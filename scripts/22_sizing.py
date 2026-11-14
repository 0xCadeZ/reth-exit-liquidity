"""Step 2: buffer sizing. Daily flows from the block-level events, then a replay of each buffer target under three
exit-demand scenarios, plus a Saturn 2 queue replay. Outputs sizing/daily_flows.csv, sizing/results.json, sizing/curve.csv.
Run: python3 -I scripts/22_sizing.py"""
import sys, os, json, csv, bisect, random, statistics as st
from collections import defaultdict
sys.path.insert(0, os.path.dirname(__file__))
from rpc import u, addr
from keccak import topic
R = os.path.join(os.path.dirname(__file__), ".."); D = os.path.join(R, "data"); RAW = os.path.join(D, "raw"); S = os.path.join(R, "sizing")
disc = json.load(open(os.path.join(D, "discovery.json"))); DP = disc["rocketDepositPool"].lower()
ED, TM, TB = topic("EtherDeposited(address,uint256,uint256)"), topic("TokensMinted(address,uint256,uint256,uint256)"), topic("TokensBurned(address,uint256,uint256,uint256)")
DEP_RECEIVED = topic("DepositReceived(address,uint256,uint256)")
state = list(csv.DictReader(open(os.path.join(D, "daily_state.csv"))))
mk_b = [int(r["block"]) for r in state]; N = len(state) - 1          # 196 full days
day_of = lambda b: bisect.bisect_right(mk_b, b) - 1
tvl = [float(r["reth_supply"]) * float(r["rate"]) for r in state]; supply = [float(r["reth_supply"]) for r in state]
actual_start = [float(r["reth_eth_collateral"]) for r in state]

# ---- daily flows (ETH) ----
bev = json.load(open(os.path.join(RAW, "buffer_events.json"))); evs = sorted(bev["logs"], key=lambda x: (x[0], x[2]))
dpl = json.load(open(os.path.join(RAW, "deposit_pool.json")))["logs"]
tx_received = {l[1] for l in dpl if l[3][0] == DEP_RECEIVED}; tx_minted = {l[1] for l in evs if l[3][0] == TM}
F = defaultdict(lambda: defaultdict(float))
bal = int(bev["start_balance_wei"]) / 1e18; cur = None
def close_tx(b):
    global bal
    T = 0.01 * tvl[max(0, day_of(b))]
    if bal > T: F[day_of(b)]["forwarded"] += bal - T; bal = T
for e in evs:
    b, tx = e[0], e[1]; d = day_of(b)
    if d < 0 or d >= N: continue
    if cur and cur != (b, tx): close_tx(cur[0])
    cur = (b, tx)
    if e[3][0] == ED:
        amt = u(e[4], 0) / 1e18; snd = addr(e[3][1])
        cls = ("mint" if (tx in tx_received or tx in tx_minted) else "recycled") if snd == DP else "node"
        F[d][cls] += amt; bal += amt
    elif e[3][0] == TB:
        eth = u(e[4], 1) / 1e18; F[d]["burn"] += eth; bal -= eth
if cur: close_tx(cur[0])
rows = []
for d in range(N):
    rows.append({"date": state[d]["date"], "tvl": tvl[d], "supply": supply[d], "actual_buffer": actual_start[d], "empty": actual_start[d] < 100,
                 "node": F[d]["node"], "recycled": F[d]["recycled"], "mint": F[d]["mint"], "burn": F[d]["burn"], "forwarded": F[d]["forwarded"]})
with open(os.path.join(S, "daily_flows.csv"), "w", newline="") as f:
    wr = csv.DictWriter(f, list(rows[0])); wr.writeheader(); wr.writerows(rows)

# ---- demand scenarios ----
funded_burn_share = [r["burn"] / r["supply"] / (float(state[i]["rate"])) for i, r in enumerate(rows) if not r["empty"]]   # rETH burned / supply
def demand_S1(): return [r["burn"] for r in rows]
def demand_S2(rng):
    out = []
    for i, r in enumerate(rows):
        if r["empty"]: out.append(max(r["burn"], rng.choice(funded_burn_share) * r["supply"] * float(state[i]["rate"])))
        else: out.append(r["burn"])
    return out
first_long = next(i for i, r in enumerate(rows) if r["date"] == "2026-08-06")
def demand_S3(rng):
    d = demand_S2(rng)
    for k in range(7): d[first_long + k] += 6826 / 7
    return d

APR = (float(state[-1]["rate"]) / float(state[0]["rate"])) ** (365 / N) - 1
def replay(target, demand, burns_first=False):
    B = min(actual_start[0], target * tvl[0]); paid_days = 0; idle = []; unpaid_total = 0.0
    for i, r in enumerate(rows):
        cap = target * r["tvl"]; inflow = r["node"] + r["recycled"] + r["mint"]; D_ = demand[i]
        if burns_first:
            pay = min(B, D_); B -= pay; B = min(B + inflow, cap)
        else:
            B = min(B + inflow, cap); pay = min(B, D_); B -= pay
        unpaid = D_ - pay; unpaid_total += unpaid; paid_days += unpaid < 1e-9; idle.append(B / r["tvl"])
    return {"share_days_paid": paid_days / N, "unpaid_eth": unpaid_total, "avg_idle_share": st.mean(idle), "yield_cost_bps_yr": st.mean(idle) * APR * 1e4}
def rippl(demand):
    c = 0.0; peak = 0.0; need = 0.0
    for i, r in enumerate(rows):
        c += r["node"] + r["recycled"] + r["mint"] - demand[i]; peak = max(peak, c); need = max(need, peak - c)
    return need
TARGETS = [0.005, 0.0075, 0.01, 0.015, 0.02, 0.03, 0.05]
RES = {"apr_used": APR, "days": N, "flows_total": {k: sum(r[k] for r in rows) for k in ("node", "recycled", "mint", "burn", "forwarded")},
       "forwarded_by_month": {}, "curve": {}}
for r in rows: RES["forwarded_by_month"][r["date"][:7]] = RES["forwarded_by_month"].get(r["date"][:7], 0) + r["forwarded"]
d1 = demand_S1()
rng = random.Random(7); runs2 = [demand_S2(rng) for _ in range(1000)]
rng = random.Random(7); runs3 = [demand_S3(rng) for _ in range(1000)]
curve_rows = []
for T in TARGETS:
    s1 = replay(T, d1); s1b = replay(T, d1, burns_first=True)
    s2 = sorted(replay(T, dm)["share_days_paid"] for dm in runs2); s3 = sorted(replay(T, dm)["share_days_paid"] for dm in runs3)
    c2 = st.median(replay(T, dm)["yield_cost_bps_yr"] for dm in runs2[:200])
    q = lambda xs, p: xs[int(p * (len(xs) - 1))]
    RES["curve"][T] = {"S1": s1, "S1_burns_first": s1b, "S2_median": q(s2, .5), "S2_p5": q(s2, .05), "S2_p95": q(s2, .95), "S2_yield_cost_bps": c2,
                       "S3_median": q(s3, .5), "S3_p5": q(s3, .05)}
    curve_rows.append([T, s1["share_days_paid"], s1b["share_days_paid"], s1["yield_cost_bps_yr"], q(s2, .5), q(s2, .05), q(s2, .95), c2, q(s3, .5)])
with open(os.path.join(S, "curve.csv"), "w", newline="") as f:
    wr = csv.writer(f); wr.writerow(["target", "S1_days_paid", "S1_burns_first", "S1_cost_bps", "S2_median", "S2_p5", "S2_p95", "S2_cost_bps", "S3_median"]); wr.writerows(curve_rows)
RES["rippl_eth"] = {"S1": rippl(d1), "S2_median": st.median(rippl(dm) for dm in runs2), "S2_p95": sorted(rippl(dm) for dm in runs2)[949], "S3_median": st.median(rippl(dm) for dm in runs3)}
RES["rippl_share_of_avg_tvl"] = {k: v / st.mean(tvl[:N]) for k, v in RES["rippl_eth"].items()}
RES["actual_history_share_days_not_empty"] = sum(1 for r in rows if not r["empty"]) / N

# ---- post-hoc (added after the pre-registered runs): buffer pre-filled to its target on May 1, S2 demand ----
def replay_full(target, demand):
    B = target * tvl[0]; paid = 0; idle = []
    for i, r in enumerate(rows):
        B = min(B + r["node"] + r["recycled"] + r["mint"], target * r["tvl"]); pay = min(B, demand[i]); B -= pay
        paid += demand[i] - pay < 1e-9; idle.append(B / r["tvl"])
    return paid / N, st.mean(idle) * APR * 1e4
RES["prefilled_S2"] = {}
for T in (0.01, 0.02, 0.03, 0.05, 0.07, 0.10):
    res = [replay_full(T, dm) for dm in runs2[:300]]; sh = sorted(x[0] for x in res)
    RES["prefilled_S2"][T] = {"days_paid_median": st.median(sh), "p5": sh[15], "p95": sh[284], "yield_cost_bps_yr": st.median(x[1] for x in res), "cost_if_always_full_bps_yr": T * APR * 1e4}
mon_in, mon_dem = defaultdict(float), defaultdict(float)
for i, r in enumerate(rows):
    m = r["date"][:7]; mon_in[m] += r["node"] + r["recycled"] + r["mint"]
    mon_dem[m] += st.mean(dm[i] for dm in runs2[:300])
RES["monthly_inflow_eth"] = dict(mon_in); RES["monthly_S2_demand_mean_eth"] = dict(mon_dem)
RES["october_forwarded_kept_at_5pct_eth"] = min(RES["forwarded_by_month"].get("2026-10", 0), 0.04 * tvl[N - 1])

# ---- Saturn 2: 1% buffer plus FIFO queue served by later inflows, no forced exits ----
def queue_waits(demand, target=0.01):
    B = min(actual_start[0], target * tvl[0]); q = []; waits = []; maxq = 0.0
    for i, r in enumerate(rows):
        inflow = r["node"] + r["recycled"] + r["mint"]
        avail = B + inflow
        while q and avail > 1e-9:                       # serve the queue first
            take = min(avail, q[0][1]); q[0][1] -= take; avail -= take
            if q[0][1] <= 1e-9: waits.append((i - q[0][0], q[0][2])); q.pop(0)
        B = min(avail, target * r["tvl"])
        pay = min(B, demand[i]); B -= pay
        if demand[i] - pay > 1e-9: q.append([i, demand[i] - pay, demand[i] - pay])
        if pay > 0: waits.append((0, pay))
        maxq = max(maxq, sum(x[1] for x in q))
    open_q = [(N - x[0], x[1]) for x in q]
    allw = waits + open_q
    tot = sum(w for _, w in allw)
    wq = sorted(allw); acc = 0; med = None; p90 = None
    for d_, w in wq:
        acc += w
        if med is None and acc >= tot / 2: med = d_
        if p90 is None and acc >= 0.9 * tot: p90 = d_
    return {"eth_weighted_median_wait_days": med, "eth_weighted_p90_wait_days": p90, "max_queue_eth": maxq, "still_queued_at_end_eth": sum(x[1] for x in q),
            "share_eth_waiting_over_7d": sum(w for d_, w in allw if d_ > 7) / tot}
RES["saturn2_S1"] = queue_waits(d1)
q2 = [queue_waits(dm) for dm in runs2[:300]]
RES["saturn2_S2"] = {k: st.median(x[k] for x in q2) for k in q2[0]}
RES["saturn2_S2_p95_of_median_wait"] = sorted(x["eth_weighted_median_wait_days"] for x in q2)[284]
# predictions
c = RES["curve"]
ok = [T for T in TARGETS if T <= 0.03 and c[T]["S1"]["share_days_paid"] >= 0.9]
RES["P10_pass"] = bool(ok); RES["P10_min_target"] = min(ok) if ok else None
RES["P11_pass"] = bool(ok and c[min(ok)]["S1"]["yield_cost_bps_yr"] < 5)
RES["P12_pass"] = all(c[T]["S2_median"] < 0.9 for T in TARGETS if T <= 0.03)
RES["P13_pass"] = RES["saturn2_S2"]["eth_weighted_median_wait_days"] < 7
json.dump(RES, open(os.path.join(S, "results.json"), "w"), indent=1, default=str)
print(json.dumps(RES, indent=1, default=str))
