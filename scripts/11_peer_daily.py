"""Daily rate, supply and market price for rETH and five peer LSTs at the first block of each UTC day.
Writes peers/daily_peers.csv (long format). Resumable. Run: python3 -I scripts/11_peer_daily.py"""
import sys, os, json, csv, threading
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(__file__))
from rpc import *
from keccak import sel, topic
R = os.path.join(os.path.dirname(__file__), ".."); P = os.path.join(R, "peers")
marks = [(r["date"], int(r["block"])) for r in csv.DictReader(open(os.path.join(R, "data", "daily_state.csv")))]
WETH = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
arg = lambda x: hex(x)[2:].rjust(64, "0")
def num(to, data, b):
    h = ecall(to, data, b); return int(h[:66], 16) if len(h) > 2 else None
def univ3(pool, token_is_0):
    def f(b):
        h = ecall(pool, sel("slot0()"), b); sp = u(h, 0) / 2**96; L = num(pool, sel("liquidity()"), b)
        if sp == 0: return None, L
        px = sp * sp                      # token1 per token0
        return (px if token_is_0 else 1 / px), L
    return f
def curve_mid(pool, i_eth, i_tok):
    def f(b):
        s = sel("get_dy(int128,int128,uint256)")
        try:
            sell = num(pool, s + arg(i_tok) + arg(i_eth) + arg(10**17), b) / 1e17   # ETH per token, selling
            buy = num(pool, s + arg(i_eth) + arg(i_tok) + arg(10**17), b) / 1e17    # tokens per ETH, buying
        except Exception: return None, None
        return (sell / buy) ** 0.5, None
    return f
TOK = {
 "rETH":  dict(token="0xae78736cd615f374d3085123a210448e74fc6393", rate=("0xae78736cd615f374d3085123a210448e74fc6393", sel("getExchangeRate()")),
               price=univ3("0x553e9c493678d8606d6a5ba284643db2110df823", True)),
 "stETH": dict(token="0xae7ab96520de3a18e5e111b5eaab095312d7fe84", rate=("0x7f39c581f595b53c5cb19bd0b3f8da6c935e2ca0", sel("stEthPerToken()")),
               price=univ3("0x109830a1aaad605bbf02a9dfa7b0b92ec2fb7daa", True), note="price and rate are for wstETH"),
 "cbETH": dict(token="0xbe9895146f7af43049ca1c1ae358b0541ea49704", rate=("0xbe9895146f7af43049ca1c1ae358b0541ea49704", sel("exchangeRate()")),
               price=univ3("0x840deeef2f115cf50da625f7368c24af6fe74410", True)),
 "mETH":  dict(token="0xd5f7838f5c461feff7fe49ea5ebaf7728bb0adfa", rate=("0xe3cbd06d7dadb3f4e6557bab7edd924cd1489e8f", sel("mETHToETH(uint256)") + arg(10**18)),
               price=univ3("0x04708077eca6bb527a5bbbd6358ffb043a9c1c14", False)),
 "ETHx":  dict(token="0xa35b1b31ce002fbf2058d22f30f95d405200a15b", rate=("0xcf5ea1b38380f6af39068375516daf40ed70d299", sel("getExchangeRate()")),
               price=curve_mid("0x59ab5a5b5d617e478a2479b0cad80da7e2831492", 0, 1)),
 "osETH": dict(token="0xf1c9acdc66974dfb6decb12aa385b9cd01190e38", rate=("0x2a261e60fb14586b474c208b1b7ac6d0f5000306", sel("convertToAssets(uint256)") + arg(10**18)),
               price=None),
}
path = os.path.join(P, "daily_peers.csv"); F = ["date", "block", "token", "rate", "supply", "price", "liquidity", "prem_bps"]
rows = list(csv.DictReader(open(path))) if os.path.exists(path) else []
done = {(r["date"], r["token"]) for r in rows}; lock = threading.Lock()
def work(name):
    t = TOK[name]; out = []
    for date, b in marks:
        if (date, name) in done: continue
        try: rate = num(t["rate"][0], t["rate"][1], b) / 1e18
        except Exception: rate = None
        try: sup = num(t["token"], sel("totalSupply()"), b) / 1e18
        except Exception: sup = None
        px = L = None
        if t["price"]:
            try: px, L = t["price"](b)
            except Exception: pass
        prem = (px / rate - 1) * 1e4 if px and rate else None
        r = {"date": date, "block": b, "token": name, "rate": rate, "supply": sup, "price": px, "liquidity": L, "prem_bps": prem}
        with lock:
            rows.append(r)
            if len(rows) % 60 == 0:
                with open(path, "w", newline="") as f: w_ = csv.DictWriter(f, F); w_.writeheader(); w_.writerows(rows)
    print(name, "done", flush=True)
with ThreadPoolExecutor(6) as ex: list(ex.map(work, TOK))
rows.sort(key=lambda r: (r["token"], r["date"]))
with open(path, "w", newline="") as f: w_ = csv.DictWriter(f, F); w_.writeheader(); w_.writerows(rows)
print("DONE", len(rows))
