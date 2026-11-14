"""Pull raw event logs for the window from public RPC. One JSON per job in data/raw/. Resumable per 10k-block chunk.
Run: python3 -I scripts/01_pull.py [job ...]"""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
from rpc import *
from keccak import topic
D = os.path.join(os.path.dirname(__file__), "..", "data"); RAW = os.path.join(D, "raw"); os.makedirs(RAW, exist_ok=True)
disc = json.load(open(os.path.join(D, "discovery.json")))
B0 = disc["b_start"]; B1 = disc["latest"] - 64  # fixed end block, ~2 epochs behind head at discovery time
RETH = "0xae78736cd615f374d3085123a210448e74fc6393"; PM = "0x000000000004444c5dc75cb358380d2e3de08a90"
JOBS = {
    "reth_transfers": dict(address=RETH, topics=[topic("Transfer(address,address,uint256)")]),
    "deposit_pool": dict(address=disc["rocketDepositPool"]),
    "balances": dict(address=disc["rocketNetworkBalances"], topics=[topic("BalancesUpdated(uint256,uint256,uint256,uint256,uint256,uint256)")]),
    "univ3_001": dict(address="0x553e9c493678d8606d6a5ba284643db2110df823", topics=[topic("Swap(address,address,int256,int256,uint160,uint128,int24)")]),
    "univ4_reth_eth": dict(address=PM, topics=[topic("Swap(bytes32,address,int128,int128,uint160,uint128,int24,uint24)"), "0x70946c979da3e5587a00b3a750cc76902d187894501ba9e8be9efd1849b6e0b7"]),
    "lido_rebase": dict(address="0xae7ab96520de3a18e5e111b5eaab095312d7fe84", topics=[topic("TokenRebased(uint256,uint256,uint256,uint256,uint256,uint256,uint256)")]),
}
def slim(lg): return [int(lg["blockNumber"], 16), lg["transactionHash"], int(lg["logIndex"], 16), lg["topics"], lg["data"]]
for name in (sys.argv[1:] or list(JOBS)):
    path = os.path.join(RAW, name + ".json")
    st = json.load(open(path)) if os.path.exists(path) else {"next": B0, "end": B1, "logs": []}
    a = st["next"]
    while a <= st["end"]:
        b = min(a + CHUNK - 1, st["end"])
        st["logs"] += [slim(x) for x in get_logs(a, b, **JOBS[name])]
        a = st["next"] = b + 1
        if (a - B0) // CHUNK % 10 == 0 or a > st["end"]:
            json.dump(st, open(path, "w")); print(name, f"{(a - B0) / (st['end'] - B0):.0%}", len(st["logs"]), flush=True)
    json.dump(st, open(path, "w")); print(name, "DONE", len(st["logs"]), flush=True)
