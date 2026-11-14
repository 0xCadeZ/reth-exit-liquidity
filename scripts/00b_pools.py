"""Find rETH DEX venues on mainnet: Uniswap v3 pools via factory, Balancer rETH/WETH, Curve rETH/ETH; Chainlink rETH/ETH rate feed."""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
from rpc import *
from keccak import sel, topic
D = os.path.join(os.path.dirname(__file__), "..", "data")
RETH = "0xae78736cd615f374d3085123a210448e74fc6393"; WETH = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
FACTORY = "0x1f98431c8ad98523631ae4a59f267346ea31f984"
def pad(a): return a[2:].lower().rjust(64, "0")
out = {"uniswap_v3": {}}
for fee in [100, 500, 3000, 10000]:
    h = ecall(FACTORY, sel("getPool(address,address,uint24)") + pad(RETH) + pad(WETH) + hex(fee)[2:].rjust(64, "0"))
    p = addr(h)
    if int(p, 16):
        liq = int(ecall(p, sel("liquidity()")), 16)
        bal_w = int(ecall(WETH, sel("balanceOf(address)") + pad(p)), 16) / 1e18; bal_r = int(ecall(RETH, sel("balanceOf(address)") + pad(p)), 16) / 1e18
        out["uniswap_v3"][fee] = {"pool": p, "weth": bal_w, "reth": bal_r}; print("univ3", fee, p, f"WETH {bal_w:.1f} rETH {bal_r:.1f}")
# Balancer: known rETH/WETH stable pool and vault
VAULT = "0xba12222222228d8ba445958a75a0704d566bf2c8"
for name, pool in [("balancer_reth_weth_v1", "0x1e19cf2d73a72ef1332c882f20534b6519be0276"), ("balancer_reth_weth_v2", "0x05ff47afada98a98982113758878f9a8b9fdda0a")]:
    pid = ecall(pool, sel("getPoolId()"))
    if len(pid) > 2:
        bal_w = int(ecall(WETH, sel("balanceOf(address)") + pad(VAULT)), 16) / 1e18
        toks = ecall(VAULT, sel("getPoolTokens(bytes32)") + pid[2:])
        # decode: offset tokens, offset balances, lastChange; tokens array
        n = u(toks, 3); tokens = [addr(toks[2 + 64*(4+i):2+64*(5+i)]) for i in range(n)]
        boff = u(toks, 1) // 32; nb = u(toks, boff); bals = [u(toks, boff + 1 + i) / 1e18 for i in range(nb)]
        out[name] = {"pool": pool, "poolId": pid, "tokens": tokens, "balances": bals}; print(name, pool, pid[:20], list(zip(tokens, [round(b,1) for b in bals])))
# Curve rETH/ETH pools: try known addresses
for name, pool in [("curve_reth_eth_ng", "0x0f3159811670c117c372428d4e69ac32325e4d0f"), ("curve_reth_weth_crypto", "0x447ddd4960d9fdbf6af9a790560d0af76795cb08")]:
    try:
        c0 = ecall(pool, sel("coins(uint256)") + "0"*64); c1 = ecall(pool, sel("coins(uint256)") + "0"*63 + "1")
        if len(c0) > 2:
            b0 = int(ecall(pool, sel("balances(uint256)") + "0"*64), 16)/1e18; b1 = int(ecall(pool, sel("balances(uint256)") + "0"*63+"1"), 16)/1e18
            out[name] = {"pool": pool, "coins": [addr(c0), addr(c1)], "balances": [b0, b1]}; print(name, pool, addr(c0), addr(c1), round(b0,1), round(b1,1))
    except Exception as e: print(name, "fail", e)
# Chainlink rETH/ETH exchange-rate feed
FEED = "0x536218f9e9eb48863970252233c8f271f554c2d0"
try:
    h = ecall(FEED, sel("latestRoundData()")); dec = int(ecall(FEED, sel("decimals()")), 16)
    print("chainlink rETH/ETH", s256("0x" + h[2+64:2+128]) / 10**dec, "updated", u(h, 3), "desc", ecall(FEED, sel("description()"))[:200])
    out["chainlink_feed"] = {"addr": FEED, "decimals": dec}
except Exception as e: print("chainlink fail", e)
# Lido stETH TokenRebased topic
print("TokenRebased topic", topic("TokenRebased(uint256,uint256,uint256,uint256,uint256,uint256,uint256)"))
print("univ3 Swap", topic("Swap(address,address,int256,int256,uint160,uint128,int24)"))
print("balancer Swap", topic("Swap(bytes32,address,address,uint256,uint256)"))
print("curve TokenExchange", topic("TokenExchange(address,int128,uint256,int128,uint256)"))
json.dump(out, open(os.path.join(D, "pools.json"), "w"), indent=1)
