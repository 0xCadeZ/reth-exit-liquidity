"""Compare rETH with five peer LSTs over the same daily marks. Inputs: peers/daily_peers.csv, peers/oseth_daily.csv,
data/daily.csv (rETH regimes). Outputs: peers/results.json and prints a summary. Run: python3 -I scripts/13_peer_compare.py"""
import sys, os, json, csv, statistics as st
from collections import defaultdict
sys.path.insert(0, os.path.dirname(__file__))
from rpc import ecall, s256, w, u
from keccak import sel
R = os.path.join(os.path.dirname(__file__), ".."); P = os.path.join(R, "peers")
rows = list(csv.DictReader(open(os.path.join(P, "daily_peers.csv"))))
fl = lambda v: float(v) if v not in ("", None, "None") else None
by = defaultdict(dict)
for r in rows: by[r["token"]][r["date"]] = {k: fl(r[k]) for k in ("block", "rate", "supply", "price", "liquidity", "prem_bps")}
os_px = {r["date"]: (float(r["price"]), float(r["vol_eth"]), int(r["swaps"])) for r in csv.DictReader(open(os.path.join(P, "oseth_daily.csv")))}
for d, x in by["osETH"].items():
    if d in os_px and x["rate"]: x["price"] = os_px[d][0]; x["prem_bps"] = (os_px[d][0] / x["rate"] - 1) * 1e4; x["vol"] = os_px[d][1]
dates = sorted(by["rETH"]); full = dates[:-1]     # last mark is a partial day for supply; keep all for price
reth = {r["date"]: r for r in csv.DictReader(open(os.path.join(R, "data", "daily.csv")))}
empty = {d for d in full if float(reth[d]["collateral_eth"]) < 100}
def longest(ds, cond):
    best = cur = 0; s = e = bs = be = None
    for d in ds:
        if cond(d): cur += 1; s = s if cur > 1 else d; e = d
        else: cur = 0
        if cur > best: best, bs, be = cur, s, e
    return best, bs, be
out = {}
for tok in ["rETH", "stETH", "cbETH", "ETHx", "osETH", "mETH"]:
    x = by[tok]; ds = [d for d in full if x.get(d, {}).get("prem_bps") is not None]
    p = [x[d]["prem_bps"] for d in ds]; ps = sorted(p)
    sup0 = next(x[d]["supply"] for d in dates if x[d]["supply"]); sup1 = x[dates[-1]]["supply"]
    r0, r1 = x[dates[0]]["rate"], x[dates[-1]]["rate"]; n = len(dates) - 1
    o = {"days_priced": len(ds), "within_10bps": sum(1 for v in p if abs(v) <= 10) / len(p), "below_minus_10": sum(1 for v in p if v < -10) / len(p),
         "median_bps": st.median(p), "p05_bps": ps[int(.05 * len(ps))], "worst_bps": ps[0], "best_bps": ps[-1],
         "longest_spell_below_minus_10": longest(full, lambda d: x.get(d, {}).get("prem_bps") is not None and x[d]["prem_bps"] < -10),
         "supply_start": sup0, "supply_end": sup1, "supply_change_pct": (sup1 / sup0 - 1) * 100,
         "rate_apr_pct": ((r1 / r0) ** (365 / n) - 1) * 100}
    if tok == "rETH":
        for name, sel_ in (("empty", lambda d: d in empty), ("funded", lambda d: d not in empty)):
            q = [x[d]["prem_bps"] for d in ds if sel_(d)]
            o[f"{name}_days"] = len(q); o[f"{name}_within_10bps"] = sum(1 for v in q if abs(v) <= 10) / len(q); o[f"{name}_median_bps"] = st.median(q)
        vw = [(x[d]["prem_bps"], float(reth[d]["prem_bps"])) for d in ds if reth[d]["prem_bps"]]
        a, b = zip(*vw); ma, mb = st.mean(a), st.mean(b)
        o["self_check_spot_vs_vwap"] = {"corr": sum((i - ma) * (j - mb) for i, j in vw) / (sum((i - ma) ** 2 for i in a) * sum((j - mb) ** 2 for j in b)) ** .5,
                                        "median_abs_diff_bps": st.median(abs(i - j) for i, j in vw)}
    if tok == "osETH": o["swap_days"] = len(os_px); o["median_daily_vol_eth"] = st.median(v[1] for v in os_px.values())
    if tok in ("mETH", "cbETH", "stETH", "rETH"): o["median_liquidity_raw"] = st.median(x[d]["liquidity"] for d in ds if x[d]["liquidity"] is not None)
    out[tok] = o
# outside check: Chainlink market feeds (stETH/ETH, cbETH/ETH) against our pool-derived premium at 12 spread days
FEEDS = {"stETH": "0x86392dc19c0b719886221c78ab11eb8cf5c52812", "cbETH": "0xf017fcb346a1885194689ba23eff2fe6fa5c483b"}
chk = {}
for tok, feed in FEEDS.items():
    desc = bytes.fromhex(ecall(feed, sel("description()"))[2:])[64:].rstrip(b"\0").decode(errors="replace")
    sample = []
    for d in full[3::16]:
        b = int(by[tok][d]["block"]); h = ecall(feed, sel("latestRoundData()"), b); px = s256("0x" + w(h, 1)) / 1e18; upd = u(h, 3)
        ours = by[tok][d]["prem_bps"]
        if tok == "stETH": feed_bps = (px - 1) * 1e4          # stETH/ETH market price; stETH rate is 1
        else: feed_bps = (px / by[tok][d]["rate"] - 1) * 1e4
        sample.append([d, round(ours, 1), round(feed_bps, 1), round(ours - feed_bps, 1)])
    chk[tok] = {"feed": feed, "description": desc, "sample": sample, "max_abs_diff_bps": max(abs(s[3]) for s in sample), "median_abs_diff_bps": st.median(abs(s[3]) for s in sample)}
out["outside_check_chainlink"] = chk
# predictions
peers = ["stETH", "cbETH", "ETHx", "osETH", "mETH"]
out["P3_reth_lowest_within_10"] = all(out["rETH"]["within_10bps"] < out[t]["within_10bps"] for t in peers)
out["P4_reth_supply_below_peer_median"] = out["rETH"]["supply_change_pct"] < st.median(out[t]["supply_change_pct"] for t in peers)
out["P4_peer_median_supply_change_pct"] = st.median(out[t]["supply_change_pct"] for t in peers)
out["P5_no_peer_30day_spell"] = all(out[t]["longest_spell_below_minus_10"][0] < 30 for t in peers)
json.dump(out, open(os.path.join(P, "results.json"), "w"), indent=1, default=str)
print(f"{'token':6} {'priced':>6} {'in10':>5} {'<-10':>5} {'med':>6} {'p05':>7} {'worst':>7} {'spell<-10':>22} {'supply%':>8} {'apr%':>5}")
for t in ["rETH"] + peers:
    o = out[t]; sp = o["longest_spell_below_minus_10"]
    print(f"{t:6} {o['days_priced']:6} {o['within_10bps']:5.0%} {o['below_minus_10']:5.0%} {o['median_bps']:6.1f} {o['p05_bps']:7.1f} {o['worst_bps']:7.1f} {str(sp[0])+' '+str(sp[1])+'..'+str(sp[2]):>22} {o['supply_change_pct']:8.1f} {o['rate_apr_pct']:5.2f}")
print(json.dumps({k: out["rETH"][k] for k in out["rETH"] if k.startswith(("empty", "funded", "self"))}, default=str))
print(json.dumps(chk, default=str)[:1500])
print({k: out[k] for k in out if k.startswith("P")})
