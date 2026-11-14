"""JSON-RPC helper for Ethereum mainnet public endpoints. Stdlib only.
Tested 2026-11-13 against ~35 public endpoints. Historical logs (10k-block ranges): Tenderly public gateway, mevblocker
(throttles hard). Archive eth_call: drpc, Blast, Tenderly. drpc and Blast reject eth_getLogs; publicnode refuses old logs."""
import json, time, urllib.request
LOG_RPCS = ["https://gateway.tenderly.co/public/mainnet", "https://mainnet.gateway.tenderly.co", "https://rpc.mevblocker.io"]
CALL_RPCS = ["https://eth.drpc.org", "https://eth-mainnet.public.blastapi.io", "https://gateway.tenderly.co/public/mainnet"]
PACE = 0.15
CHUNK = 10_000
def _post(url, method, params, timeout):
    req = urllib.request.Request(url, data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(),
                                 headers={"Content-Type": "application/json", "User-Agent": "reth-mint/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)
def call(method, params, retries=6, timeout=30, rpcs=None):
    rpcs = rpcs or (LOG_RPCS if method == "eth_getLogs" else CALL_RPCS)
    err = None
    for k in range(retries):
        try:
            time.sleep(PACE)
            out = _post(rpcs[k % len(rpcs)], method, params, timeout)
            if "result" in out and out["result"] is not None: return out
            err = RuntimeError(str(out.get("error"))[:200])
        except Exception as e:
            err = e
        time.sleep(0.6 * (k + 1))
    raise err
def _logs(frm, to, topics, address):
    f = {"fromBlock": hex(frm), "toBlock": hex(to)}
    if topics: f["topics"] = topics
    if address: f["address"] = address
    try:
        return call("eth_getLogs", [f], retries=4)["result"]
    except Exception:
        if to - frm < 2: raise
        mid = (frm + to) // 2
        return _logs(frm, mid, topics, address) + _logs(mid + 1, to, topics, address)
def get_logs(frm, to, topics=None, address=None, progress=None):
    out = []
    a = frm
    while a <= to:
        b = min(a + CHUNK - 1, to)
        out += _logs(a, b, topics, address)
        if progress: progress(b, len(out))
        a = b + 1
    return out
def ecall(to, data, block="latest"):
    if isinstance(block, int): block = hex(block)
    return call("eth_call", [{"to": to, "data": data}, block])["result"]
def balance(a, block="latest"):
    if isinstance(block, int): block = hex(block)
    return int(call("eth_getBalance", [a, block])["result"], 16)
_ts = {}
def ts(bn):
    if bn not in _ts: _ts[bn] = int(call("eth_getBlockByNumber", [hex(bn), False])["result"]["timestamp"], 16)
    return _ts[bn]
def latest(): return int(call("eth_blockNumber", [])["result"], 16)
def block_at(t, lo, hi):
    while lo < hi:
        mid = (lo + hi) // 2
        if ts(mid) < t: lo = mid + 1
        else: hi = mid
    return lo
def s256(h):
    v = int(h, 16); return v - (1 << 256) if v >= (1 << 255) else v
def u(h, i): return int(h[2 + 64 * i: 2 + 64 * (i + 1)], 16)
def w(h, i): return h[2 + 64 * i: 2 + 64 * (i + 1)]
def addr(h): return "0x" + h[-40:]
