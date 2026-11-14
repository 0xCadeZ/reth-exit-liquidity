"""Daily on-chain state at the first block of each UTC day: rETH supply, exchange rate, rETH contract ETH (burn collateral),
deposit pool balance, validator queue length, Chainlink rETH/ETH feed. Archive eth_call. Writes data/daily_state.csv. Resumable."""
import sys, os, json, csv, datetime as dt
sys.path.insert(0, os.path.dirname(__file__))
from rpc import *
from keccak import sel
D = os.path.join(os.path.dirname(__file__), "..", "data")
disc = json.load(open(os.path.join(D, "discovery.json")))
RETH = disc["rocketTokenRETH"]; DP = disc["rocketDepositPool"]; FEED = "0x536218f9e9eb48863970252233c8f271f554c2d0"
B0 = disc["b_start"]; B1 = disc["latest"] - 64
t0 = int(dt.datetime(2026, 5, 1, tzinfo=dt.UTC).timestamp())
def mark(t, guess):
    """first block with timestamp >= t, starting from a guess (12s slots)."""
    b = guess
    for _ in range(8):
        d = ts(b) - t
        if d == 0: break
        nb = b - round(d / 12)
        if nb == b: break
        b = nb
    while ts(b) >= t: b -= 1
    while ts(b) < t: b += 1
    return b
def val(to, sig, blk, signed=False):
    try:
        h = ecall(to, sel(sig), blk)
        if len(h) <= 2: return ""
        return s256(h) if signed else int(h, 16)
    except Exception:
        return ""
path = os.path.join(D, "daily_state.csv")
rows = list(csv.DictReader(open(path))) if os.path.exists(path) else []
done = {r["date"] for r in rows}
F = ["date", "block", "ts", "reth_supply", "rate", "reth_eth_collateral", "dp_balance", "queue_len", "express_queue_len", "node_balance", "chainlink_rate", "max_pool"]
b = int(rows[-1]["block"]) if rows else B0; day = 0
while True:
    t = t0 + 86400 * day; date = dt.datetime.fromtimestamp(t, dt.UTC).strftime("%Y-%m-%d")
    if date in done: day += 1; continue
    if t > ts(B1): break   # the next day has not started at the end block
    b = mark(t, max(b, B0) + (7170 if rows else 0))
    cl = ""
    try:
        h = ecall(FEED, sel("latestRoundData()"), b); cl = s256("0x" + w(h, 1)) / 1e18
    except Exception: pass
    r = {"date": date, "block": b, "ts": ts(b), "reth_supply": val(RETH, "totalSupply()", b) / 1e18, "rate": val(RETH, "getExchangeRate()", b) / 1e18,
         "reth_eth_collateral": balance(RETH, b) / 1e18, "dp_balance": (val(DP, "getBalance()", b) or 0) / 1e18,
         "queue_len": val(DP, "getTotalQueueLength()", b), "express_queue_len": val(DP, "getExpressQueueLength()", b),
         "node_balance": (val(DP, "getNodeBalance()", b) or 0) / 1e18, "chainlink_rate": cl,
         "max_pool": (val(disc["rocketDAOProtocolSettingsDeposit"], "getMaximumDepositPoolSize()", b) or 0) / 1e18}
    rows.append(r); done.add(date); day += 1
    with open(path, "w", newline="") as f:
        wr = csv.DictWriter(f, F); wr.writeheader(); wr.writerows(rows)
    if day % 10 == 0: print(date, b, round(r["reth_supply"]), round(r["rate"], 5), round(r["reth_eth_collateral"]), round(r["dp_balance"]), r["queue_len"], flush=True)
print("DONE", len(rows), flush=True)
