"""Discovery: resolve Rocket Pool contracts from RocketStorage, block marks for the window, sample events."""
import sys, os, json, datetime as dt, calendar
sys.path.insert(0, os.path.dirname(__file__))
from rpc import *
from keccak import keccak256, topic, sel
D = os.path.join(os.path.dirname(__file__), "..", "data")
STORAGE = "0x1d8f8f00cfa6758d7bE78336684788Fb0ee0Fa46"
def storage_addr(name):
    key = keccak256(b"contract.address" + name.encode()).hex()
    return addr(ecall(STORAGE, sel("getAddress(bytes32)") + key))
out = {}
for n in ["rocketTokenRETH", "rocketDepositPool", "rocketNetworkBalances", "rocketVault", "rocketDAOProtocolSettingsDeposit", "rocketMinipoolQueue", "rocketDepositPoolQueue"]:
    out[n] = storage_addr(n); print(n, out[n])
L = latest(); print("latest", L, ts(L))
t0 = calendar.timegm(dt.datetime(2026, 5, 1).timetuple()); b0 = block_at(t0, L - 2_000_000, L)
print("block at 2026-05-01", b0, dt.datetime.fromtimestamp(ts(b0), dt.UTC))
out["latest"] = L; out["b_start"] = b0
reth = out["rocketTokenRETH"]
# supply, exchange rate now
print("rETH totalSupply", int(ecall(reth, sel("totalSupply()")), 16) / 1e18)
print("getExchangeRate", int(ecall(reth, sel("getExchangeRate()")), 16) / 1e18)
print("rETH contract ETH balance (excess for burns)", balance(reth) / 1e18)
dp = out["rocketDepositPool"]
print("deposit pool getBalance", int(ecall(dp, sel("getBalance()")), 16) / 1e18)
print("deposit pool getExcessBalance", int(ecall(dp, sel("getExcessBalance()")), 16) / 1e18 if len(ecall(dp, sel("getExcessBalance()"))) > 2 else "n/a")
ds = out["rocketDAOProtocolSettingsDeposit"]
for fn in ["getDepositEnabled()", "getMaximumDepositPoolSize()", "getMinimumDeposit()", "getDepositFee()", "getAssignDepositsEnabled()"]:
    h = ecall(ds, sel(fn)); print(fn, int(h, 16) if len(h) > 2 else "n/a")
# sample recent events per contract (last ~3 days) to learn shapes
for n in ["rocketDepositPool", "rocketNetworkBalances"]:
    logs = get_logs(L - 20000, L, address=out[n])
    sigs = {}
    for lg in logs: sigs.setdefault(lg["topics"][0], []).append(lg)
    print(n, "events last 20k blocks:", {k: len(v) for k, v in sigs.items()})
    for k, v in sigs.items():
        print("  ", k, "topics", len(v[0]["topics"]), "data words", (len(v[0]["data"]) - 2) // 64, "example", v[0]["topics"][1:], v[0]["data"][:200])
# known candidate signatures
for s in ["DepositReceived(address,uint256,uint256)", "DepositAssigned(address,uint256,uint256)", "DepositRecycled(address,uint256,uint256)", "ExcessWithdrawn(address,uint256,uint256)",
          "BalancesSubmitted(address,uint256,uint256,uint256,uint256,uint256,uint256)", "BalancesUpdated(uint256,uint256,uint256,uint256,uint256,uint256)", "BalancesUpdated(uint256,uint256,uint256,uint256)",
          "TokensMinted(address,uint256,uint256,uint256)", "TokensBurned(address,uint256,uint256,uint256)", "EtherDeposited(address,uint256,uint256)"]:
    print(topic(s), s)
json.dump(out, open(os.path.join(D, "discovery.json"), "w"), indent=1)
