"""Peer LSTs: verify token contracts and rate functions on-chain, find Uniswap v3 WETH pools, list top transfer counterparties (last ~7 days)."""
import sys, os, json
from collections import Counter
sys.path.insert(0, os.path.dirname(__file__))
from rpc import *
from keccak import sel, topic
D = os.path.join(os.path.dirname(__file__), "..", "peers")
WETH = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"; FACTORY = "0x1f98431c8ad98523631ae4a59f267346ea31f984"
pad = lambda a: a[2:].lower().rjust(64, "0")
def sym(a):
    try:
        h = ecall(a, sel("symbol()")); b = bytes.fromhex(h[2:])
        return b[64:64 + int.from_bytes(b[32:64], "big")].decode() if len(b) >= 96 else b.rstrip(b"\0").decode()
    except Exception as e: return f"ERR {e}"[:60]
PEERS = {
 "wstETH": dict(token="0x7f39c581f595b53c5cb19bd0b3f8da6c935e2ca0", rate_to="0x7f39c581f595b53c5cb19bd0b3f8da6c935e2ca0", rate_sig="stEthPerToken()"),
 "cbETH":  dict(token="0xbe9895146f7af43049ca1c1ae358b0541ea49704", rate_to="0xbe9895146f7af43049ca1c1ae358b0541ea49704", rate_sig="exchangeRate()"),
 "ETHx":   dict(token="0xa35b1b31ce002fbf2058d22f30f95d405200a15b", rate_to="0xcf5ea1b38380f6af39068375516daf40ed70d299", rate_sig="getExchangeRate()"),
 "osETH":  dict(token="0xf1c9acdc66974dfb6decb12aa385b9cd01190e38", rate_to="0x2a261e60fb14586b474c208b1b7ac6d0f5000306", rate_sig="convertToAssets(uint256)", arg=10**18),
 "mETH":   dict(token="0xd5f7838f5c461feff7fe49ea5ebaf7728bb0adfa", rate_to="0xe3cbd06d7dadb3f4e6557bab7edd924cd1489e8f", rate_sig="mETHToETH(uint256)", arg=10**18),
 "rETH":   dict(token="0xae78736cd615f374d3085123a210448e74fc6393", rate_to="0xae78736cd615f374d3085123a210448e74fc6393", rate_sig="getExchangeRate()"),
}
L = latest(); T = topic("Transfer(address,address,uint256)")
for n, p in PEERS.items():
    data = sel(p["rate_sig"]) + (hex(p["arg"])[2:].rjust(64, "0") if "arg" in p else "")
    try: rate = int(ecall(p["rate_to"], data), 16) / 1e18
    except Exception as e: rate = f"ERR {str(e)[:60]}"
    sup = int(ecall(p["token"], sel("totalSupply()")), 16) / 1e18
    print(f"\n== {n}: symbol={sym(p['token'])} supply={sup:,.0f} rate={rate}")
    p["univ3"] = {}
    for fee in (100, 500, 3000, 10000):
        pool = addr(ecall(FACTORY, sel("getPool(address,address,uint24)") + pad(p["token"]) + pad(WETH) + hex(fee)[2:].rjust(64, "0")))
        if int(pool, 16):
            bw = int(ecall(WETH, sel("balanceOf(address)") + pad(pool)), 16) / 1e18; bt = int(ecall(p["token"], sel("balanceOf(address)") + pad(pool)), 16) / 1e18
            p["univ3"][fee] = pool; print(f"  univ3 {fee}: {pool} WETH {bw:,.1f} token {bt:,.1f}")
    logs = get_logs(L - 50000, L, topics=[T], address=p["token"])
    c = Counter(); v = Counter()
    for lg in logs:
        val = int(lg["data"], 16) / 1e18 if len(lg["data"]) > 2 else 0
        for a in (addr(lg["topics"][1]), addr(lg["topics"][2])): c[a] += 1; v[a] += val
    print(f"  transfers last 50k blocks: {len(logs)}")
    for a, k in c.most_common(10):
        code = call("eth_getCode", [a, "latest"])["result"]
        print(f"   {a} n={k} vol={v[a]:,.0f} {'contract' if len(code) > 2 else 'EOA'} {sym(a) if len(code) > 2 else ''}")
json.dump(PEERS, open(os.path.join(D, "peers.json"), "w"), indent=1)
