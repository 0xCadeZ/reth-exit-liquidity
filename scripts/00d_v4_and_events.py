"""Identify Uniswap v4 rETH pool ids (from receipts of recent rETH<->PoolManager transfers), name Saturn deposit pool events, queue getters."""
import sys, os, json
from collections import Counter
sys.path.insert(0, os.path.dirname(__file__))
from rpc import *
from keccak import topic, sel
D = os.path.join(os.path.dirname(__file__), "..", "data")
RETH = "0xae78736cd615f374d3085123a210448e74fc6393"; PM = "0x000000000004444c5dc75cb358380d2e3de08a90"
T = topic("Transfer(address,address,uint256)"); V4SWAP = topic("Swap(bytes32,address,int128,int128,uint160,uint128,int24,uint24)")
print("v4 swap topic", V4SWAP)
L = latest(); pad = lambda a: "0x" + a[2:].rjust(64, "0")
logs = get_logs(L - 50000, L, topics=[T, None, pad(PM)], address=RETH) + get_logs(L - 50000, L, topics=[T, pad(PM)], address=RETH)
txs = list({lg["transactionHash"] for lg in logs}); print("v4 txs", len(txs))
ids = Counter(); ex = {}
for h in txs[:40]:
    rc = call("eth_getTransactionReceipt", [h])["result"]
    for lg in rc["logs"]:
        if lg["address"].lower() == PM and lg["topics"][0] == V4SWAP:
            ids[lg["topics"][1]] += 1; ex[lg["topics"][1]] = lg["data"]
for i, n in ids.most_common(8):
    d = ex[i]; a0, a1 = s256("0x" + w(d, 0)), s256("0x" + w(d, 1)); sp = u(d, 2); fee = u(d, 5)
    print(i, n, "amt0", a0 / 1e18, "amt1", a1 / 1e18, "price1per0", (sp / 2**96) ** 2, "fee", fee)
names = ["DepositReceived(address,uint256,uint256)", "DepositRecycled(address,uint256,uint256)", "DepositAssigned(address,uint256,uint256)", "ExcessWithdrawn(address,uint256,uint256)",
         "FundsRequested(address,uint256,uint256,bool,uint256)", "FundsAssigned(address,uint256,uint256)", "QueueExited(address,uint256)", "CreditWithdrawn(address,uint256,uint256)",
         "FundsRequested(address,uint256,uint256,uint256,uint256)", "FundsAssigned(address,uint256,uint256,uint256)"]
for s in names: print(topic(s)[:12], s)
DP = json.load(open(os.path.join(D, "discovery.json")))["rocketDepositPool"]
for fn in ["getTotalQueueLength()", "getStandardQueueLength()", "getExpressQueueLength()", "getMinipoolQueueLength()", "getQueueIndex()", "getNodeBalance()", "getUserBalance()", "getMaximumDepositAmount()", "getReservedBalance()"]:
    try:
        h = ecall(DP, sel(fn)); print(fn, int(h, 16) if len(h) > 2 else "n/a")
    except Exception as e: print(fn, "revert")
json.dump({"v4_ids": dict(ids)}, open(os.path.join(D, "v4_ids.json"), "w"), indent=1)
