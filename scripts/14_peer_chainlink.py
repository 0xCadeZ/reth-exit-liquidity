"""Sensitivity: market price from Chainlink market feeds (token/ETH) at every daily mark, for the tokens that have one.
These feeds update on a 0.5-2% deviation or a 24 h heartbeat, so they are coarse; used only to check the pool-based numbers.
Writes peers/chainlink_daily.csv."""
import sys, os, csv
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(__file__))
from rpc import ecall, s256, w
from keccak import sel
R = os.path.join(os.path.dirname(__file__), ".."); P = os.path.join(R, "peers")
FEEDS = {"rETH": "0x536218f9E9Eb48863970252233c8F271f554C2d0", "stETH": "0x86392dC19c0b719886221c78AB11eb8Cf5c52812",
         "cbETH": "0xF017fcB346A1885194689bA23Eff2fE6fA5C483b", "ETHx": "0xC5f8c4aB091Be1A899214c0C3636ca33DcA0C547", "mETH": "0x5b563107C8666d2142C216114228443B94152362"}
rows = [r for r in csv.DictReader(open(os.path.join(P, "daily_peers.csv"))) if r["token"] in FEEDS]
def get(r):
    h = ecall(FEEDS[r["token"]], sel("latestRoundData()"), int(r["block"])); px = s256("0x" + w(h, 1)) / 1e18
    rate = 1.0 if r["token"] == "stETH" else float(r["rate"])        # stETH/ETH feed prices stETH, whose rate is 1
    return {"date": r["date"], "token": r["token"], "feed_price": px, "feed_prem_bps": (px / rate - 1) * 1e4, "updated_at": int(h[2 + 64 * 3: 2 + 64 * 4], 16)}
with ThreadPoolExecutor(4) as ex: out = list(ex.map(get, rows))
with open(os.path.join(P, "chainlink_daily.csv"), "w", newline="") as f:
    wr = csv.DictWriter(f, list(out[0])); wr.writeheader(); wr.writerows(sorted(out, key=lambda x: (x["token"], x["date"])))
print("ok", len(out))
