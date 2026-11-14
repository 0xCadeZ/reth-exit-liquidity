"""osETH market price: Balancer v3 osETH/waEthWETH swaps over the window, fee-adjusted, waEthWETH converted to WETH
with the wrapper's convertToAssets at the day's first block. Writes peers/oseth_swaps.json and peers/oseth_daily.csv."""
import sys, os, json, csv
from collections import defaultdict
sys.path.insert(0, os.path.dirname(__file__))
from rpc import *
from keccak import sel, topic
R = os.path.join(os.path.dirname(__file__), ".."); P = os.path.join(R, "peers")
marks = [(r["date"], int(r["block"])) for r in csv.DictReader(open(os.path.join(R, "data", "daily_state.csv")))]
V3 = "0xba1333333333a1ba1108e8412f11850a5c319ba9"; POOL = "0x57c23c58b1d8c3292c15becf07c62c5c52457a42"; OS = "0xf1c9acdc66974dfb6decb12aa385b9cd01190e38"
SW = topic("Swap(address,address,address,uint256,uint256,uint256,uint256)")
disc = json.load(open(os.path.join(R, "data", "discovery.json"))); B0, B1 = marks[0][1], disc["latest"] - 64
fp = os.path.join(P, "oseth_swaps.json")
if os.path.exists(fp): logs = json.load(open(fp))
else:
    logs = [[int(l["blockNumber"], 16), l["topics"], l["data"]] for l in get_logs(B0, B1, topics=[SW, "0x" + POOL[2:].rjust(64, "0")], address=V3)]
    json.dump(logs, open(fp, "w"))
print("swaps", len(logs))
other = {addr(t[2]) for b, t, d in logs} | {addr(t[3]) for b, t, d in logs}; other.discard(OS); print("other tokens", other)
WA = other.pop()
blocks = [b for _, b in marks]
import bisect
conv = {}
def wa_rate(i):
    if i not in conv: conv[i] = int(ecall(WA, sel("convertToAssets(uint256)") + hex(10**18)[2:].rjust(64, "0"), blocks[i]), 16) / 1e18
    return conv[i]
day = defaultdict(lambda: [0.0, 0.0, 0])   # sum(px*vol), vol, n
for b, t, d in logs:
    i = bisect.bisect_right(blocks, b) - 1
    if i < 0: continue
    a_in, a_out, fee = u(d, 0) / 1e18, u(d, 1) / 1e18, u(d, 2) / 1e18
    if addr(t[2]) == OS:   # sold osETH for waWETH
        px = a_out * wa_rate(i) / (a_in * (1 - fee)); vol = a_out * wa_rate(i)
    else:                  # bought osETH with waWETH
        px = a_in * wa_rate(i) * (1 - fee) / a_out; vol = a_in * wa_rate(i)
    x = day[marks[i][0]]; x[0] += px * vol; x[1] += vol; x[2] += 1
with open(os.path.join(P, "oseth_daily.csv"), "w", newline="") as f:
    w_ = csv.writer(f); w_.writerow(["date", "price", "vol_eth", "swaps"])
    for date, _ in marks:
        if date in day: x = day[date]; w_.writerow([date, x[0] / x[1], x[1], x[2]])
print("days with swaps", len(day))
