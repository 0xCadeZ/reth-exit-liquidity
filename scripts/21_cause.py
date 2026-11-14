"""Step 1: block-level rETH buffer, inflow sources, refill natural experiments, arbitrage drain, hourly direction test.
Inputs: data/raw/{buffer_events,deposit_pool,reth_transfers,univ3_001,univ4_reth_eth,balances}.json, data/daily_state.csv.
Outputs: cause/results.json, cause/refills.csv, cause/hourly.csv. Run: python3 -I scripts/21_cause.py"""
import sys, os, json, csv, bisect, statistics as st
from collections import defaultdict, Counter
sys.path.insert(0, os.path.dirname(__file__))
from rpc import s256, u, w, addr
from keccak import topic
R = os.path.join(os.path.dirname(__file__), ".."); D = os.path.join(R, "data"); RAW = os.path.join(D, "raw"); C = os.path.join(R, "cause")
disc = json.load(open(os.path.join(D, "discovery.json")))
DP = disc["rocketDepositPool"].lower()
ED, TM, TB = topic("EtherDeposited(address,uint256,uint256)"), topic("TokensMinted(address,uint256,uint256,uint256)"), topic("TokensBurned(address,uint256,uint256,uint256)")
DEP_RECEIVED, DEP_RECYCLED = topic("DepositReceived(address,uint256,uint256)"), topic("DepositRecycled(address,uint256,uint256)")
EMPTY, REFILL, HOUR = 1.0, 10.0, 3600

# ---- block -> timestamp by interpolation between daily marks (12 s slots, missed slots make small errors) ----
state = list(csv.DictReader(open(os.path.join(D, "daily_state.csv"))))
mk_b = [int(r["block"]) for r in state]; mk_t = [int(r["ts"]) for r in state]
def bts(b):
    i = max(0, min(len(mk_b) - 2, bisect.bisect_right(mk_b, b) - 1))
    return mk_t[i] + (b - mk_b[i]) * (mk_t[i + 1] - mk_t[i]) / (mk_b[i + 1] - mk_b[i])

# ---- events ----
bev = json.load(open(os.path.join(RAW, "buffer_events.json"))); assert bev["next"] > bev["end"], "pull incomplete"
evs = sorted(bev["logs"], key=lambda x: (x[0], x[2]))
dpl = json.load(open(os.path.join(RAW, "deposit_pool.json")))["logs"]
tx_received = {l[1] for l in dpl if l[3][0] == DEP_RECEIVED}; tx_recycled = {l[1] for l in dpl if l[3][0] == DEP_RECYCLED}
tx_minted = {l[1] for l in evs if l[3][0] == TM}
def label(sender, tx):
    if sender == DP:
        return "mint" if (tx in tx_received or tx in tx_minted) else "recycled"
    return "node"

# ---- arbitrage burns: rETH reached the burner from a DEX pool in the same transaction ----
POOLS = {"0x553e9c493678d8606d6a5ba284643db2110df823", "0xa4e0faa58465a2d369aa21b3e42d43374c6f9613", "0xf0e02cf61b31260fd5ae527d58be16312bda59b1",
         "0x000000000004444c5dc75cb358380d2e3de08a90", "0xba12222222228d8ba445958a75a0704d566bf2c8", "0xba1333333333a1ba1108e8412f11850a5c319ba9",
         "0x0f3159811670c117c372428d4e69ac32325e4d0f", "0x447ddd4960d9fdbf6af9a790560d0af76795cb08"}
tr = json.load(open(os.path.join(RAW, "reth_transfers.json")))["logs"]
tx_from_pool = {l[1] for l in tr if addr(l[3][1]) in POOLS}

# ---- protocol rate steps and DEX swaps (mid price / rate) ----
bal = json.load(open(os.path.join(RAW, "balances.json")))["logs"]
steps = sorted((l[0], u(l[4], 1) / u(l[4], 3)) for l in bal); sb = [s[0] for s in steps]
rate_at = lambda b: steps[max(0, bisect.bisect_right(sb, b) - 1)][1]
swaps = []
for l in json.load(open(os.path.join(RAW, "univ3_001.json")))["logs"]:
    sp = u(l[4], 2) / 2**96
    if sp: swaps.append((l[0], (sp * sp / rate_at(l[0]) - 1) * 1e4))
for l in json.load(open(os.path.join(RAW, "univ4_reth_eth.json")))["logs"]:
    sp = u(l[4], 2) / 2**96
    if sp: swaps.append((l[0], (1 / (sp * sp) / rate_at(l[0]) - 1) * 1e4))
swaps.sort(); sw_t = [bts(b) for b, _ in swaps]; sw_p = [p for _, p in swaps]
def prem_window(t0, t1):
    i, j = bisect.bisect_left(sw_t, t0), bisect.bisect_right(sw_t, t1)
    return sw_p[i:j]
def prem_last(t):
    i = bisect.bisect_right(sw_t, t) - 1
    return sw_p[i] if i >= 0 else None

# ---- rebuild balance, per transaction ----
# The rETH contract forwards ETH above its 1% target to the deposit pool without an event, so cap at the target after
# each transaction; then re-anchor to the true balance at every daily reading (the cap uses day-start supply and rate).
def target(b):
    i = max(0, bisect.bisect_right(mk_b, b) - 1); r = state[i]; return 0.01 * float(r["reth_supply"]) * float(r["rate"])
balance = int(bev["start_balance_wei"]) / 1e18
by_tx = defaultdict(list)
for e in evs: by_tx[(e[0], e[1])].append(e)
txs = sorted(by_tx, key=lambda k: (k[0], min(e[2] for e in by_tx[k])))
inflow_by_class = Counter(); burns_eth = 0.0; mints_reth = []  # (t, reth)
series = []    # (block, t, balance_after, in_eth, in_class, out_eth, arb_out_eth)
for (b, tx) in txs:
    ein = defaultdict(float); eout = 0.0; arb = 0.0
    for e in by_tx[(b, tx)]:
        t0 = e[3][0]
        if t0 == ED:
            amt = u(e[4], 0) / 1e18; cl = label(addr(e[3][1]), tx); ein[cl] += amt; inflow_by_class[cl] += amt
        elif t0 == TB:
            eth = u(e[4], 1) / 1e18; eout += eth
            if tx in tx_from_pool: arb += eth
        elif t0 == TM:
            mints_reth.append((bts(b), u(e[4], 0) / 1e18))
    tin = sum(ein.values()); balance += tin - eout; burns_eth += eout
    balance = min(balance, target(b))
    cls = max(ein, key=ein.get) if ein else None
    series.append((b, bts(b), balance, tin, cls, eout, arb, dict(ein)))

# ---- check against the daily balance readings, then re-anchor each day ----
sb2 = [s[0] for s in series]
def bal_at(b):
    i = bisect.bisect_right(sb2, b) - 1
    return series[i][2] if i >= 0 else int(bev["start_balance_wei"]) / 1e18
resid = [(r["date"], float(r["reth_eth_collateral"]) - bal_at(int(r["block"]))) for r in state if int(r["block"]) <= bev["end"]]
absr = [abs(x) for _, x in resid]
RES = {"events": len(evs), "txs": len(txs), "inflow_eth_by_class": dict(inflow_by_class), "burn_eth": burns_eth, "forwarded_note": "excess above 1% forwarded without event",
       "recon_daily_before_anchor": {"n": len(resid), "max_abs_eth": max(absr), "median_abs_eth": st.median(absr), "days_within_0_01_eth": sum(1 for x in absr if x < 0.01),
                       "worst": sorted(resid, key=lambda x: -abs(x[1]))[:5]}}
offs = [float(r["reth_eth_collateral"]) - bal_at(int(r["block"])) for r in state]
series = [(b, t, bal + offs[max(0, bisect.bisect_right(mk_b, b) - 1)] * (b >= mk_b[0]), *rest) for (b, t, bal, *rest) in series]
# outside check: true balance at 60 random event blocks
import random
from rpc import balance as eth_balance
random.seed(7); pick = random.sample(range(len(series)), 60)
RETH = "0xae78736cd615f374d3085123a210448e74fc6393"
chk = [abs(eth_balance(RETH, series[i][0]) / 1e18 - series[i][2]) for i in pick]
RES["recon_random_blocks"] = {"n": 60, "max_abs_eth": max(chk), "median_abs_eth": st.median(chk), "within_0_01": sum(1 for x in chk if x < 0.01), "within_1": sum(1 for x in chk if x < 1)}
print(json.dumps(RES, indent=1, default=str))
json.dump(RES, open(os.path.join(C, "results_recon.json"), "w"), indent=1, default=str)
print(json.dumps(RES, indent=1, default=str))
if "--recon-only" in sys.argv: sys.exit()

# ---- refills ----
mt = [m[0] for m in mints_reth]; mcum = [0.0]
for _, a in mints_reth: mcum.append(mcum[-1] + a)
def minted(t0, t1):
    return mcum[bisect.bisect_right(mt, t1)] - mcum[bisect.bisect_left(mt, t0)]
refills = []
prev = int(bev["start_balance_wei"]) / 1e18
for k, (b, t, bal_after, tin, cls, eout, arb, ein) in enumerate(series):
    if prev < EMPTY and bal_after >= REFILL and tin > 0:
        j = k + 1
        while j < len(series) and series[j][2] >= EMPTY: j += 1
        end_t = series[j][1] if j < len(series) else None
        drained_out = sum(s[5] for s in series[k + 1:j + 1]); drained_arb = sum(s[6] for s in series[k + 1:j + 1])
        pre, post = prem_window(t - 6 * HOUR, t), prem_window(t + 1, t + 6 * HOUR)
        refills.append({"block": b, "time": t, "class": cls, "inflow_eth": tin, "inflow_by_class": ein, "balance_after": bal_after,
                        "prem_pre6h": st.median(pre) if pre else None, "prem_post6h": st.median(post) if post else None, "n_pre": len(pre), "n_post": len(post),
                        "mint_24h_before": minted(t - 24 * HOUR, t), "mint_24h_after": minted(t + 1, t + 24 * HOUR),
                        "mint_7d_before": minted(t - 7 * 86400, t), "mint_7d_after": minted(t + 1, t + 7 * 86400),
                        "hours_until_empty": (end_t - t) / HOUR if end_t else None, "drained_by_burns_eth": drained_out, "drained_by_arb_eth": drained_arb})
    prev = bal_after
# exact check of every refill against the true balance before and after its block
for r in refills:
    b = r["block"]; pre_b, post_b = eth_balance(RETH, b - 1) / 1e18, eth_balance(RETH, b) / 1e18
    r["true_before"], r["true_after"] = pre_b, post_b; r["confirmed"] = pre_b < EMPTY and post_b >= REFILL
RES["refill_candidates"] = len(refills); RES["refills_confirmed"] = sum(r["confirmed"] for r in refills)
refills = [r for r in refills if r["confirmed"]]
with open(os.path.join(C, "refills.csv"), "w", newline="") as f:
    keys = [k for k in refills[0] if k != "inflow_by_class"]; wr = csv.DictWriter(f, keys, extrasaction="ignore"); wr.writeheader(); wr.writerows(refills)
def summarise(rs):
    both = [r for r in rs if r["prem_pre6h"] is not None and r["prem_post6h"] is not None]
    d = [r["prem_post6h"] - r["prem_pre6h"] for r in both]
    big = [r for r in rs if r["inflow_eth"] >= 100]
    hrs = [r["hours_until_empty"] for r in rs if r["hours_until_empty"] is not None]
    out = sum(r["drained_by_burns_eth"] for r in rs)
    return {"n": len(rs), "n_with_swaps_both_sides": len(both), "median_prem_change_bps": st.median(d) if d else None, "share_prem_up": sum(1 for x in d if x > 0) / len(d) if d else None,
            "median_prem_pre": st.median(r["prem_pre6h"] for r in both) if both else None, "median_prem_post": st.median(r["prem_post6h"] for r in both) if both else None,
            "n_100eth_plus": len(big), "share_100eth_mint_up_24h": sum(1 for r in big if r["mint_24h_after"] > r["mint_24h_before"]) / len(big) if big else None,
            "median_mint_24h_before_100eth": st.median(r["mint_24h_before"] for r in big) if big else None, "median_mint_24h_after_100eth": st.median(r["mint_24h_after"] for r in big) if big else None,
            "share_100eth_mint_up_7d": sum(1 for r in big if r["mint_7d_after"] > r["mint_7d_before"]) / len(big) if big else None,
            "median_hours_until_empty": st.median(hrs) if hrs else None, "share_empty_within_24h": sum(1 for h in hrs if h <= 24) / len(hrs) if hrs else None,
            "arb_share_of_drain": sum(r["drained_by_arb_eth"] for r in rs) / out if out else None}
exo = [r for r in refills if r["class"] in ("recycled", "node")]; endo = [r for r in refills if r["class"] == "mint"]
RES["refills"] = {"all": summarise(refills), "exogenous": summarise(exo), "mint_driven": summarise(endo), "by_class": dict(Counter(r["class"] for r in refills))}
p6 = RES["refills"]["exogenous"]; RES["P6_pass"] = bool(p6["median_prem_change_bps"] is not None and p6["median_prem_change_bps"] >= 5 and p6["share_prem_up"] >= 0.7)
RES["P7_pass"] = bool(p6["share_100eth_mint_up_24h"] is not None and p6["share_100eth_mint_up_24h"] >= 0.6)

# ---- P8: FIFO, ETH that arrived while DEX was > 5 bps under the rate: how much left through burns within 24 h, and how much of that was arbitrage ----
queue = []   # [t_in, eth_left, under_discount]
disc_in = disc_burn24 = disc_arb24 = 0.0
for (b, t, bal_after, tin, cls, eout, arb, ein) in series:
    if tin > 0:
        p = prem_last(t); flag = p is not None and p < -5
        queue.append([t, tin, flag]); disc_in += tin if flag else 0
    rem = eout; arb_frac = arb / eout if eout else 0
    while rem > 1e-12 and queue:
        q = queue[0]; take = min(rem, q[1]); q[1] -= take; rem -= take
        if q[2] and t - q[0] <= 24 * HOUR: disc_burn24 += take; disc_arb24 += take * arb_frac
        if q[1] <= 1e-12: queue.pop(0)
RES["P8"] = {"eth_in_under_discount": disc_in, "share_burned_within_24h": disc_burn24 / disc_in if disc_in else None,
             "arb_share_of_those_burns": disc_arb24 / disc_burn24 if disc_burn24 else None}
RES["P8_pass"] = bool(RES["P8"]["share_burned_within_24h"] and RES["P8"]["share_burned_within_24h"] > 0.5 and RES["P8"]["arb_share_of_those_burns"] > 0.5)

# ---- P9: hourly direction test with Newey-West (24 lags) standard errors ----
t0, t1 = series[0][1], series[-1][1]
hours = list(range(int(t0 // HOUR) + 25, int(t1 // HOUR) - 25))
st_t = [s[1] for s in series]
def bal_t(t):
    i = bisect.bisect_right(st_t, t) - 1
    return series[i][2] if i >= 0 else int(bev["start_balance_wei"]) / 1e18
rows = []
for h in hours:
    t = h * HOUR; funded = 1.0 if bal_t(t) >= REFILL else 0.0
    rows.append((minted(t, t + 24 * HOUR), funded, minted(t - 24 * HOUR, t), prem_last(t)))
with open(os.path.join(C, "hourly.csv"), "w", newline="") as f:
    wr = csv.writer(f); wr.writerow(["mint_next24", "funded", "mint_prev24", "prem_last"]); wr.writerows(rows)
def ols_nw(y, X, L):
    n, k = len(y), len(X[0])
    XtX = [[sum(X[r][a] * X[r][b] for r in range(n)) for b in range(k)] for a in range(k)]
    A = [row[:] + [float(i == j) for j in range(k)] for i, row in enumerate(XtX)]
    for c in range(k):
        p = max(range(c, k), key=lambda r: abs(A[r][c])); A[c], A[p] = A[p], A[c]; pv = A[c][c]; A[c] = [v / pv for v in A[c]]
        for r in range(k):
            if r != c: fr = A[r][c]; A[r] = [v - fr * q for v, q in zip(A[r], A[c])]
    inv = [row[k:] for row in A]
    beta = [sum(inv[a][b] * sum(X[r][b] * y[r] for r in range(n)) for b in range(k)) for a in range(k)]
    e = [y[r] - sum(X[r][a] * beta[a] for a in range(k)) for r in range(n)]
    S = [[sum(X[r][a] * X[r][b] * e[r] * e[r] for r in range(n)) for b in range(k)] for a in range(k)]
    for l in range(1, L + 1):
        wl = 1 - l / (L + 1)
        for a in range(k):
            for b in range(k):
                g = sum(X[r][a] * e[r] * e[r - l] * X[r - l][b] for r in range(l, n)); S[a][b] += wl * (g + sum(X[r][b] * e[r] * e[r - l] * X[r - l][a] for r in range(l, n)))
    V = [[sum(inv[a][i] * sum(S[i][j] * inv[j][b] for j in range(k)) for i in range(k)) for b in range(k)] for a in range(k)]
    return {"n": n, "beta": beta, "t_nw": [beta[a] / V[a][a] ** 0.5 for a in range(k)]}
RES["P9_mint_next24_on_funded_and_mint_prev24"] = ols_nw([r[0] for r in rows], [[1.0, r[1], r[2]] for r in rows], 24)
pr = [r for r in rows if r[3] is not None]
RES["P9b_with_premium_control"] = ols_nw([r[0] for r in pr], [[1.0, r[1], r[2], r[3]] for r in pr], 24)
b9 = RES["P9_mint_next24_on_funded_and_mint_prev24"]; RES["P9_pass"] = bool(b9["beta"][1] > 0 and b9["t_nw"][1] > 2)
RES["share_hours_funded"] = sum(r[1] for r in rows) / len(rows)
json.dump(RES, open(os.path.join(C, "results.json"), "w"), indent=1, default=str)
print(json.dumps(RES, indent=1, default=str))
