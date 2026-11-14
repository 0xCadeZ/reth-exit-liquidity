"""Pull EtherDeposited, TokensMinted and TokensBurned from the rETH contract over the window, plus the balance at the block
before the window. Writes data/raw/buffer_events.json. Resumable per 10k-block chunk."""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
from rpc import *
from keccak import topic
D = os.path.join(os.path.dirname(__file__), "..", "data"); RAW = os.path.join(D, "raw")
disc = json.load(open(os.path.join(D, "discovery.json"))); B0 = disc["b_start"]; B1 = disc["latest"] - 64
RETH = "0xae78736cd615f374d3085123a210448e74fc6393"
TOP = [[topic("EtherDeposited(address,uint256,uint256)"), topic("TokensMinted(address,uint256,uint256,uint256)"), topic("TokensBurned(address,uint256,uint256,uint256)")]]
path = os.path.join(RAW, "buffer_events.json")
st = json.load(open(path)) if os.path.exists(path) else {"next": B0, "end": B1, "start_balance_wei": str(balance(RETH, B0 - 1)), "logs": []}
a = st["next"]
while a <= st["end"]:
    b = min(a + CHUNK - 1, st["end"])
    st["logs"] += [[int(l["blockNumber"], 16), l["transactionHash"], int(l["logIndex"], 16), l["topics"], l["data"]] for l in get_logs(a, b, topics=TOP, address=RETH)]
    a = st["next"] = b + 1
    if (a - B0) // CHUNK % 20 == 0 or a > st["end"]:
        json.dump(st, open(path, "w")); print(f"{(a - B0) / (st['end'] - B0):.0%}", len(st["logs"]), flush=True)
json.dump(st, open(path, "w")); print("DONE", len(st["logs"]))
