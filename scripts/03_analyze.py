"""Daily series, route ladder, tests and reconciliations for the rETH mint study.
Inputs: data/raw/*.json, data/daily_state.csv, data/coingecko_reth_eth.json. Outputs: data/daily.csv, data/results.json.
Run: python3 -I scripts/03_analyze.py"""
import sys, os, json, csv, bisect, statistics as st, datetime as dt
from collections import defaultdict, Counter
sys.path.insert(0, os.path.dirname(__file__))
from rpc import ecall, s256, u, w, addr
from keccak import topic, sel
D = os.path.join(os.path.dirname(__file__), "..", "data"); RAW = os.path.join(D, "raw")
disc = json.load(open(os.path.join(D, "discovery.json")))
def raw(n):
    s = json.load(open(os.path.join(RAW, n + ".json"))); assert s["next"] > s["end"], n + " incomplete"
    return s["logs"], s["end"]
state = list(csv.DictReader(open(os.path.join(D, "daily_state.csv"))))
for r in state:
    for k in r:
        if k != "date": r[k] = float(r[k]) if r[k] not in ("", None) else None
marks = [int(r["block"]) for r in state]; dates = [r["date"] for r in state]; N = len(state)
B0 = disc["b_start"]; assert marks[0] == B0, (marks[0], B0)
def day(b): return bisect.bisect_right(marks, b) - 1
ZERO = "0x" + "0" * 64
MINT_FEE = 0.0005

# ---- protocol rate as a step function of block (BalancesUpdated) ----
bal, B1 = raw("balances")
steps = sorted((lg[0], u(lg[4], 1) / u(lg[4], 3)) for lg in bal)   # (block, totalEth / rethSupply)
sb = [s[0] for s in steps]
def rate_at(b):
    i = bisect.bisect_right(sb, b) - 1
    return steps[i][1] if i >= 0 else state[0]["rate"]
# check the step series against getExchangeRate() at daily marks
chk = [abs(rate_at(m) / r["rate"] - 1) * 1e4 for m, r in zip(marks, state)]
print(f"rate steps {len(steps)}; step-vs-getExchangeRate max diff {max(chk):.4f} bps")

# ---- mints and burns from raw rETH transfers ----
tr, _ = raw("reth_transfers")
POOLS = {"0x553e9c493678d8606d6a5ba284643db2110df823", "0xa4e0faa58465a2d369aa21b3e42d43374c6f9613", "0xf0e02cf61b31260fd5ae527d58be16312bda59b1",
         "0x000000000004444c5dc75cb358380d2e3de08a90", "0xba12222222228d8ba445958a75a0704d566bf2c8", "0xba1333333333a1ba1108e8412f11850a5c319ba9",
         "0x0f3159811670c117c372428d4e69ac32325e4d0f", "0x447ddd4960d9fdbf6af9a790560d0af76795cb08"}
bytx = defaultdict(list)
for b, tx, li, tp, data in tr: bytx[tx].append((li, addr(tp[1]), addr(tp[2]), int(data, 16), b))
Z = "0x" + "0" * 40
mint_w = burn_w = 0
d_mint = [0.0] * N; d_burn = [0.0] * N; d_mint_n = [0] * N; d_burn_n = [0] * N
d_mint_pool = [0.0] * N; d_burn_pool = [0.0] * N   # minted then sold into a DEX pool / bought from a DEX pool then burned
minters = Counter(); burners = Counter(); mint_sizes = []; burn_sizes = []
for tx, ts_ in bytx.items():
    net = Counter(); m = bn = 0; b = ts_[0][4]
    for li, f, t, v, _ in ts_:
        if f == Z: m += v
        if t == Z: bn += v
        if f != Z: net[f] -= v
        if t != Z: net[t] += v
    i = day(b)
    if i < 0 or i >= N: continue
    if m:
        mint_w += m; d_mint[i] += m / 1e18; d_mint_n[i] += 1; mint_sizes.append(m / 1e18)
        into_pool = sum(v for a, v in net.items() if a in POOLS and v > 0)
        d_mint_pool[i] += min(m, into_pool) / 1e18
        for a, v in net.items():
            if v > 0 and a not in POOLS: minters[a] += min(v, m) / 1e18
    if bn:
        burn_w += bn; d_burn[i] += bn / 1e18; d_burn_n[i] += 1; burn_sizes.append(bn / 1e18)
        from_pool = -sum(v for a, v in net.items() if a in POOLS and v < 0)
        d_burn_pool[i] += min(bn, from_pool) / 1e18
        for a, v in net.items():
            if v < 0 and a not in POOLS: burners[a] += min(-v, bn) / 1e18

# ---- DEX swaps: per-swap mid price against the protocol rate at that block ----
v3, _ = raw("univ3_001"); v4, _ = raw("univ4_reth_eth")
swaps = []   # (block, mid ETH per rETH, vol_eth, user_sold_reth, liquidity, venue, exec_price)
for b, tx, li, tp, data in v3:     # token0 rETH, token1 WETH
    a0, a1 = s256("0x" + w(data, 0)), s256("0x" + w(data, 1)); sp = u(data, 2) / 2**96; L = u(data, 3)
    if a0 == 0 or a1 == 0: continue
    swaps.append((b, sp * sp, abs(a1) / 1e18, a0 > 0, L, "v3", abs(a1) / abs(a0), sp))
for b, tx, li, tp, data in v4:     # currency0 native ETH, currency1 rETH; deltas from the swapper's side
    a0, a1 = s256("0x" + w(data, 0)), s256("0x" + w(data, 1)); sp = u(data, 2) / 2**96; L = u(data, 3)
    if a0 == 0 or a1 == 0: continue
    swaps.append((b, 1 / (sp * sp), abs(a0) / 1e18, a1 < 0, L, "v4", abs(a0) / abs(a1), sp))
swaps.sort()
d_vol = [0.0] * N; d_pv = [0.0] * N; d_sell = [0.0] * N; d_below = [0.0] * N; d_band = [0.0] * N; d_above = [0.0] * N
d_slip = [[] for _ in range(N)]; d_v3 = [0.0] * N; last_mid_before = [None] * N; lm = None; j = 0
for b, mid, vol, sold, L, ven, px, sp in swaps:
    i = day(b)
    if i < 0 or i >= N: continue
    prem = (mid / rate_at(b) - 1) * 1e4
    d_vol[i] += vol; d_pv[i] += prem * vol
    if sold: d_sell[i] += vol
    if ven == "v3": d_v3[i] += vol
    if prem < 0: d_below[i] += vol
    elif prem <= MINT_FEE * 1e4: d_band[i] += vol
    else: d_above[i] += vol
    if L > 0:   # price impact of buying rETH with 10 ETH against in-range liquidity
        dy = 10e18
        imp = (1 + dy / (L * sp)) ** 2 - 1 if ven == "v3" else (1 + dy * sp / L) ** 2 - 1
        d_slip[i].append(imp * 1e4)
for i in range(N):
    while j < len(swaps) and swaps[j][0] < marks[i]: lm = swaps[j][1]; j += 1
    last_mid_before[i] = lm

# ---- stETH yield from Lido TokenRebased ----
lr, _ = raw("lido_rebase")
reb = sorted((lg[0], u(lg[4], 0), (u(lg[4], 4) / u(lg[4], 3)) / (u(lg[4], 2) / u(lg[4], 1)) - 1) for lg in lr)  # block, timeElapsed, growth
def steth_apr(i, n=30):
    xs = [(te, g) for b, te, g in reb if b < marks[i]][-n:]
    if len(xs) < n: return None
    tot = 1.0; secs = 0
    for te, g in xs: tot *= 1 + g; secs += te
    return tot ** (365 * 86400 / secs) - 1
def reth_apr(i, n=30):
    if i < n: return None
    return (state[i]["rate"] / state[i - n]["rate"]) ** (365 / n) - 1

# ---- deposit pool events ----
dp, _ = raw("deposit_pool")
T = {topic("DepositReceived(address,uint256,uint256)"): "dep", topic("FundsRequested(address,uint256,uint256,bool,uint256)"): "req",
     topic("FundsAssigned(address,uint256,uint256)"): "asg", topic("QueueExited(address,uint256)"): "exit"}
d_dep = [0.0] * N; d_req = [0.0] * N; d_asg = [0.0] * N; d_exit = [0] * N
for b, tx, li, tp, data in dp:
    k = T.get(tp[0]); i = day(b)
    if not k or i < 0 or i >= N: continue
    if k == "dep": d_dep[i] += u(data, 0) / 1e18
    elif k == "req": d_req[i] += u(data, 1) / 1e18
    elif k == "asg": d_asg[i] += u(data, 0) / 1e18
    else: d_exit[i] += 1

# ---- daily table + route ladder (10 ETH, one-year hold, rETH exits at the protocol rate) ----
rows = []
for i in range(N):
    s = state[i]; vol = d_vol[i]; prem = d_pv[i] / vol if vol else None
    ya, ys = reth_apr(i), steth_apr(i)
    slip = st.median(d_slip[i]) if d_slip[i] else None
    r = {"date": dates[i], "block": marks[i], "rate": s["rate"], "reth_supply": s["reth_supply"], "collateral_eth": s["reth_eth_collateral"],
         "dp_balance": s["dp_balance"], "max_pool": s["max_pool"], "queue_len": s["queue_len"], "mint_reth": d_mint[i], "burn_reth": d_burn[i],
         "mint_n": d_mint_n[i], "burn_n": d_burn_n[i], "mint_into_pool": d_mint_pool[i], "burn_from_pool": d_burn_pool[i],
         "dep_eth": d_dep[i], "funds_requested_eth": d_req[i], "funds_assigned_eth": d_asg[i], "queue_exits": d_exit[i],
         "dex_vol_eth": vol, "dex_sell_share": d_sell[i] / vol if vol else None, "prem_bps": prem,
         "vol_below": d_below[i], "vol_band": d_band[i], "vol_above": d_above[i], "slip10_bps": slip,
         "reth_apr30": ya, "steth_apr30": ys}
    if ya is not None and ys is not None and prem is not None:
        dex_cost = prem / 1e4 + 0.000125 + (slip or 0) / 1e4
        r["ret_mint"] = (1 + ya) / (1 + MINT_FEE) - 1; r["ret_dex"] = (1 + ya) / (1 + dex_cost) - 1
        r["ret_steth"] = ys; r["ret_native"] = ys / 0.9
        r["best_liquid"] = max(("mint", r["ret_mint"]), ("dex", r["ret_dex"]), ("steth", r["ret_steth"]), key=lambda x: x[1])[0]
        r["best_reth_route"] = "mint" if r["ret_mint"] > r["ret_dex"] else "dex"
    rows.append(r)
complete = rows[:-1] if marks[-1] + 7000 > B1 else rows   # drop a partial last day
F = list(dict.fromkeys(k for r in rows for k in r))
with open(os.path.join(D, "daily.csv"), "w", newline="") as f:
    wr = csv.DictWriter(f, F); wr.writeheader(); wr.writerows(rows)

# ---- OLS helper ----
def ols(y, X):
    n, k = len(y), len(X[0])
    XtX = [[sum(X[r][a] * X[r][b] for r in range(n)) for b in range(k)] for a in range(k)]
    Xty = [sum(X[r][a] * y[r] for r in range(n)) for a in range(k)]
    A = [row[:] + [float(i == j) for j in range(k)] for i, row in enumerate(XtX)]
    for c in range(k):
        p = max(range(c, k), key=lambda r: abs(A[r][c])); A[c], A[p] = A[p], A[c]
        pv = A[c][c]; A[c] = [v / pv for v in A[c]]
        for r in range(k):
            if r != c: fr = A[r][c]; A[r] = [v - fr * q for v, q in zip(A[r], A[c])]
    inv = [row[k:] for row in A]; beta = [sum(inv[a][b] * Xty[b] for b in range(k)) for a in range(k)]
    res = [y[r] - sum(X[r][a] * beta[a] for a in range(k)) for r in range(n)]
    ybar = sum(y) / n; sse = sum(e * e for e in res); sst = sum((v - ybar) ** 2 for v in y)
    s2 = sse / (n - k); se = [(s2 * inv[a][a]) ** 0.5 for a in range(k)]
    return {"n": n, "beta": beta, "t": [b / s if s else None for b, s in zip(beta, se)], "r2": 1 - sse / sst if sst else None}

R = {"window": [dates[0], dates[-1]], "end_block": B1, "days": len(complete)}
tm, tb = sum(d_mint), sum(d_burn)
R["totals"] = {"mint_reth": tm, "burn_reth": tb, "net_reth": tm - tb, "mint_txs": sum(d_mint_n), "burn_txs": sum(d_burn_n),
               "mint_into_pool_share": sum(d_mint_pool) / tm, "burn_from_pool_share": sum(d_burn_pool) / tb,
               "supply_start": state[0]["reth_supply"], "supply_end_day": state[-1]["reth_supply"],
               "median_mint_size": st.median(mint_sizes), "median_burn_size": st.median(burn_sizes),
               "top10_minter_share": sum(v for _, v in minters.most_common(10)) / tm, "top10_burner_share": sum(v for _, v in burners.most_common(10)) / tb,
               "dex_vol_eth": sum(d_vol), "dex_v3_share": sum(d_v3) / sum(d_vol), "dex_sell_share": sum(d_sell) / sum(d_vol),
               "vol_below_rate": sum(d_below) / sum(d_vol), "vol_in_band": sum(d_band) / sum(d_vol), "vol_above_ceiling": sum(d_above) / sum(d_vol),
               "dep_eth": sum(d_dep), "funds_assigned_eth": sum(d_asg), "funds_requested_eth": sum(d_req)}
R["top_minters"] = minters.most_common(8); R["top_burners"] = burners.most_common(8)
# monthly
mon = defaultdict(lambda: defaultdict(float))
for r in rows:
    m = mon[r["date"][:7]]
    for k in ("mint_reth", "burn_reth", "dex_vol_eth", "dep_eth", "funds_assigned_eth"): m[k] += r[k]
    if r["prem_bps"] is not None: m["pv"] += r["prem_bps"] * r["dex_vol_eth"]
    m["queue_end"] = r["queue_len"]; m["supply_end"] = r["reth_supply"]; m["coll_end"] = r["collateral_eth"]
    for k in ("reth_apr30", "steth_apr30"):
        if r[k] is not None: m[k] = r[k]
R["monthly"] = {k: {**dict(v), "prem_bps": v["pv"] / v["dex_vol_eth"] if v["dex_vol_eth"] else None} for k, v in sorted(mon.items())}

# plumbing: was the pool ever full or closed?
R["plumbing"] = {"days_pool_at_cap": sum(1 for r in complete if r["dp_balance"] >= r["max_pool"] > 0), "max_dp_balance": max(r["dp_balance"] for r in rows),
                 "min_max_pool": min(r["max_pool"] for r in rows), "min_collateral": min(r["collateral_eth"] for r in rows),
                 "days_collateral_below_100": sum(1 for r in rows if r["collateral_eth"] < 100),
                 "queue_start": rows[0]["queue_len"], "queue_end": rows[-1]["queue_len"], "queue_min": min(r["queue_len"] for r in rows), "queue_max": max(r["queue_len"] for r in rows)}

# prediction 1: premium days vs discount days
pd_ = [r for r in complete if r["prem_bps"] is not None]
prem_days = [r["mint_reth"] for r in pd_ if r["prem_bps"] > 0]; disc_days = [r["mint_reth"] for r in pd_ if r["prem_bps"] < 0]
R["prediction1"] = {"premium_days": len(prem_days), "discount_days": len(disc_days), "no_swap_days": len(complete) - len(pd_),
                    "mean_mint_premium": st.mean(prem_days) if prem_days else None, "mean_mint_discount": st.mean(disc_days) if disc_days else None,
                    "median_mint_premium": st.median(prem_days) if prem_days else None, "median_mint_discount": st.median(disc_days) if disc_days else None}
p = R["prediction1"]
p["mean_ratio"] = p["mean_mint_premium"] / p["mean_mint_discount"] if disc_days and p["mean_mint_discount"] else None
p["median_ratio"] = p["median_mint_premium"] / p["median_mint_discount"] if disc_days and p["median_mint_discount"] else None
p["pass"] = bool(p["mean_ratio"] and p["mean_ratio"] >= 3)
# prediction 2: band
inb = [r for r in pd_ if 0 <= r["prem_bps"] <= 5]; inb_fee = [r for r in pd_ if -1.25 <= r["prem_bps"] <= 6.25]
ps = sorted(r["prem_bps"] for r in pd_)
q = lambda f: ps[min(len(ps) - 1, int(f * len(ps)))]
R["prediction2"] = {"days": len(pd_), "share_in_band_0_5": len(inb) / len(pd_), "share_in_fee_adjusted_band": len(inb_fee) / len(pd_),
                    "prem_p05": q(.05), "prem_p25": q(.25), "prem_median": q(.5), "prem_p75": q(.75), "prem_p95": q(.95), "prem_min": ps[0], "prem_max": ps[-1],
                    "pass": len(inb) / len(pd_) >= 0.9}
# mint days above the ceiling
hi = [r for r in pd_ if r["prem_bps"] > 5]; lo = [r for r in pd_ if r["prem_bps"] <= 5]
R["ceiling"] = {"days_above_5bps": len(hi), "mint_share_on_those_days": sum(r["mint_reth"] for r in hi) / sum(r["mint_reth"] for r in pd_),
                "mean_mint_above": st.mean(r["mint_reth"] for r in hi) if hi else None, "mean_mint_at_or_below": st.mean(r["mint_reth"] for r in lo) if lo else None}

# OLS
xs = [(complete[i], complete[i - 1]) for i in range(1, len(complete)) if complete[i]["prem_bps"] is not None and complete[i - 1]["prem_bps"] is not None]
R["ols_mint_on_lagged_prem"] = ols([a["mint_reth"] for a, b in xs], [[1.0, b["prem_bps"]] for a, b in xs])
R["ols_mint_on_prem_same_day"] = ols([a["mint_reth"] for a, b in xs], [[1.0, a["prem_bps"]] for a, b in xs])
R["ols_net_on_lagged_prem"] = ols([a["mint_reth"] - a["burn_reth"] for a, b in xs], [[1.0, b["prem_bps"]] for a, b in xs])
ys_ = [(a, b) for a, b in xs if a.get("ret_mint") is not None]
if len(ys_) > 20:
    R["ols_mint_on_prem_and_yield_gap"] = ols([a["mint_reth"] for a, b in ys_], [[1.0, b["prem_bps"], (a["reth_apr30"] - a["steth_apr30"]) * 1e4] for a, b in ys_])
    R["ols_net_on_yield_gap"] = ols([a["mint_reth"] - a["burn_reth"] for a, b in ys_], [[1.0, (a["reth_apr30"] - a["steth_apr30"]) * 1e4] for a, b in ys_])

# ladder
lad = [r for r in complete if "best_liquid" in r]
R["ladder"] = {"days": len(lad), "best_liquid": dict(Counter(r["best_liquid"] for r in lad)), "best_reth_route": dict(Counter(r["best_reth_route"] for r in lad)),
               "mean_ret": {k: st.mean(r[k] for r in lad) for k in ("ret_mint", "ret_dex", "ret_steth", "ret_native")},
               "mean_reth_apr30": st.mean(r["reth_apr30"] for r in lad), "mean_steth_apr30": st.mean(r["steth_apr30"] for r in lad),
               "mean_gap_bps": st.mean((r["reth_apr30"] - r["steth_apr30"]) * 1e4 for r in lad),
               "days_reth_yield_above_steth": sum(1 for r in lad if r["reth_apr30"] > r["steth_apr30"]),
               "mean_dex_edge_over_mint_bps": st.mean((r["ret_dex"] - r["ret_mint"]) * 1e4 for r in lad),
               "median_slip10_bps": st.median(r["slip10_bps"] for r in lad if r["slip10_bps"] is not None)}
R["reth_apr_window"] = (state[-1]["rate"] / state[0]["rate"]) ** (365 / (N - 1)) - 1
tot = 1.0; secs = 0
for b, te, g in reb: tot *= 1 + g; secs += te
R["steth_apr_window"] = tot ** (365 * 86400 / secs) - 1

# ---- reconciliations ----
s0 = int(ecall(disc["rocketTokenRETH"], sel("totalSupply()"), B0 - 1), 16); s1 = int(ecall(disc["rocketTokenRETH"], sel("totalSupply()"), B1), 16)
R["recon_supply"] = {"supply_before_start_wei": str(s0), "supply_at_end_wei": str(s1), "mints_wei": str(mint_w), "burns_wei": str(burn_w),
                     "diff_wei": str(s1 - s0 - (mint_w - burn_w)), "exact": s1 - s0 == mint_w - burn_w}
idx = list(range(5, N, max(1, (N - 5) // 10)))[:10]
cl = [(dates[i], (state[i]["chainlink_rate"] / state[i]["rate"] - 1) * 1e4) for i in idx if state[i]["chainlink_rate"]]
cl_all = [abs(state[i]["chainlink_rate"] / state[i]["rate"] - 1) * 1e4 for i in range(N) if state[i]["chainlink_rate"]]
R["recon_chainlink"] = {"sample": cl, "max_abs_bps_sample": max(abs(x) for _, x in cl), "max_abs_bps_all_days": max(cl_all), "pass": max(abs(x) for _, x in cl) <= 5}
cg = {dt.datetime.fromtimestamp(t / 1000, dt.UTC).strftime("%Y-%m-%d"): v for t, v in json.load(open(os.path.join(D, "coingecko_reth_eth.json")))["prices"] if t % 86400000 == 0}
cgs = [(dates[i], (last_mid_before[i] / cg[dates[i]] - 1) * 1e4) for i in idx if dates[i] in cg and last_mid_before[i]]
cg_all = [abs(last_mid_before[i] / cg[dates[i]] - 1) * 1e4 for i in range(N) if dates[i] in cg and last_mid_before[i]]
R["recon_coingecko"] = {"sample": cgs, "max_abs_bps_sample": max(abs(x) for _, x in cgs), "median_abs_bps_all_days": st.median(cg_all),
                        "share_days_within_10bps": sum(1 for x in cg_all if x <= 10) / len(cg_all), "pass": max(abs(x) for _, x in cgs) <= 10}
# ---- post-hoc (not pre-registered): burn-collateral regimes. "Empty" = under 100 ETH in the rETH contract at the day's first block ----
EMPTY = 100
def summ(x):
    return {"days": len(x), "mean_prem_bps": st.mean(r["prem_bps"] for r in x), "median_prem_bps": st.median(r["prem_bps"] for r in x),
            "mint_per_day": st.mean(r["mint_reth"] for r in x), "median_mint_per_day": st.median(r["mint_reth"] for r in x),
            "burn_per_day": st.mean(r["burn_reth"] for r in x), "share_days_in_band_0_5": sum(1 for r in x if 0 <= r["prem_bps"] <= 5) / len(x),
            "share_days_prem_above_5": sum(1 for r in x if r["prem_bps"] > 5) / len(x), "share_days_prem_above_0": sum(1 for r in x if r["prem_bps"] > 0) / len(x),
            "dex_vol_per_day": st.mean(r["dex_vol_eth"] for r in x), "share_days_dex_beats_mint": sum(1 for r in x if r["prem_bps"] / 1e4 + 0.000125 + (r["slip10_bps"] or 0) / 1e4 < MINT_FEE) / len(x)}
emp = [r for r in complete if r["collateral_eth"] < EMPTY]; fun = [r for r in complete if r["collateral_eth"] >= EMPTY]
R["regime_empty"] = summ(emp); R["regime_funded"] = summ(fun)
R["regime_mint_ratio_funded_over_empty"] = R["regime_funded"]["mint_per_day"] / R["regime_empty"]["mint_per_day"]
R["regime_empty_spans"] = []
i = 0
while i < len(complete):
    if complete[i]["collateral_eth"] < EMPTY:
        j2 = i
        while j2 + 1 < len(complete) and complete[j2 + 1]["collateral_eth"] < EMPTY: j2 += 1
        R["regime_empty_spans"].append([complete[i]["date"], complete[j2]["date"], j2 - i + 1]); i = j2 + 1
    else: i += 1
# event study: 7 days before and after each change of regime
ev = {"to_empty": [], "to_funded": []}
for i in range(7, len(complete) - 7):
    a, b = complete[i - 1]["collateral_eth"] < EMPTY, complete[i]["collateral_eth"] < EMPTY
    if a != b:
        pre, post = complete[i - 7:i], complete[i:i + 7]
        f = lambda x, k: st.mean(r[k] for r in x)
        ev["to_empty" if b else "to_funded"].append({"date": complete[i]["date"], "prem_pre": f(pre, "prem_bps"), "prem_post": f(post, "prem_bps"),
                                                     "mint_pre": f(pre, "mint_reth"), "mint_post": f(post, "mint_reth"), "burn_pre": f(pre, "burn_reth"), "burn_post": f(post, "burn_reth")})
R["event_study_collateral"] = ev
# the long empty spell and its end
long_ = max(R["regime_empty_spans"], key=lambda x: x[2]) if R["regime_empty_spans"] else None
R["longest_empty_span"] = long_
# counterfactual: with a zero deposit fee, on how many funded days is minting cheaper than the DEX at 10 ETH?
R["fee_counterfactual_funded_days"] = {"mint_cheaper_now": sum(1 for r in fun if r["prem_bps"] / 1e4 + 0.000125 + (r["slip10_bps"] or 0) / 1e4 > MINT_FEE) / len(fun),
                                       "mint_cheaper_at_zero_fee": sum(1 for r in fun if r["prem_bps"] / 1e4 + 0.000125 + (r["slip10_bps"] or 0) / 1e4 > 0) / len(fun)}
# independent check of the DEX discount: the Chainlink RETH/ETH feed is a market-price feed, so compare it with the DEX mid, both against the rate
pairs = [((last_mid_before[i] / state[i]["rate"] - 1) * 1e4, (state[i]["chainlink_rate"] / state[i]["rate"] - 1) * 1e4, dates[i]) for i in range(N) if last_mid_before[i] and state[i]["chainlink_rate"]]
dif = [abs(a - b) for a, b, _ in pairs]
mx, my = st.mean(a for a, b, _ in pairs), st.mean(b for a, b, _ in pairs)
cov = sum((a - mx) * (b - my) for a, b, _ in pairs); vx = sum((a - mx) ** 2 for a, b, _ in pairs); vy = sum((b - my) ** 2 for a, b, _ in pairs)
pe = [(a, b) for (a, b, d_), r in zip(pairs, rows) if r["collateral_eth"] < EMPTY]
R["recon_dex_vs_chainlink_market"] = {"days": len(pairs), "median_abs_diff_bps": st.median(dif), "share_within_10bps": sum(1 for x in dif if x <= 10) / len(dif),
                                      "correlation": cov / (vx * vy) ** 0.5, "sample": [(d_, round(a, 1), round(b, 1)) for a, b, d_ in pairs[5::19]][:10],
                                      "empty_days_mean_dex_bps": st.mean(a for a, b in pe), "empty_days_mean_chainlink_bps": st.mean(b for a, b in pe)}
R["ols_mint_on_funded_dummy"] = ols([r["mint_reth"] for r in complete], [[1.0, float(r["collateral_eth"] >= EMPTY)] for r in complete])
R["burn_tx_note"] = {"burn_txs": sum(d_burn_n), "median_burn_reth": st.median(burn_sizes), "burn_txs_under_1_reth": sum(1 for x in burn_sizes if x < 1) / len(burn_sizes),
                     "burn_volume_from_txs_over_100": sum(x for x in burn_sizes if x >= 100) / sum(burn_sizes)}
json.dump(R, open(os.path.join(D, "results.json"), "w"), indent=1, default=str)
print(json.dumps({k: R[k] for k in R if k.startswith(("regime", "event", "longest", "fee_", "recon", "burn_tx", "prediction", "plumbing"))}, indent=1, default=str))
