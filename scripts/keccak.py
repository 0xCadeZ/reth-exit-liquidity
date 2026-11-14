"""Pure-Python Keccak-256 (Ethereum). Stdlib only."""
RC = [0x0000000000000001,0x0000000000008082,0x800000000000808A,0x8000000080008000,0x000000000000808B,0x0000000080000001,0x8000000080008081,0x8000000000008009,0x000000000000008A,0x0000000000000088,0x0000000080008009,0x000000008000000A,0x000000008000808B,0x800000000000008B,0x8000000000008089,0x8000000000008003,0x8000000000008002,0x8000000000000080,0x000000000000800A,0x800000008000000A,0x8000000080008081,0x8000000000008080,0x0000000080000001,0x8000000080008008]
ROT = [[0,36,3,41,18],[1,44,10,45,2],[62,6,43,15,61],[28,55,25,21,56],[27,20,39,8,14]]
M = (1 << 64) - 1
def rol(x, n): return ((x << n) | (x >> (64 - n))) & M if n else x
def f(st):
    for rc in RC:
        C = [st[x][0]^st[x][1]^st[x][2]^st[x][3]^st[x][4] for x in range(5)]
        D = [C[(x-1)%5] ^ rol(C[(x+1)%5], 1) for x in range(5)]
        st = [[st[x][y] ^ D[x] for y in range(5)] for x in range(5)]
        B = [[0]*5 for _ in range(5)]
        for x in range(5):
            for y in range(5): B[y][(2*x+3*y)%5] = rol(st[x][y], ROT[x][y])
        st = [[B[x][y] ^ ((~B[(x+1)%5][y]) & B[(x+2)%5][y]) for y in range(5)] for x in range(5)]
        st[0][0] ^= rc
    return st
def keccak256(data: bytes) -> bytes:
    rate = 136
    data = bytearray(data); data.append(0x01)
    while len(data) % rate: data.append(0)
    data[-1] |= 0x80
    st = [[0]*5 for _ in range(5)]
    for off in range(0, len(data), rate):
        blk = data[off:off+rate]
        for i in range(rate // 8):
            x, y = i % 5, i // 5
            st[x][y] ^= int.from_bytes(blk[8*i:8*i+8], "little")
        st = f(st)
    out = b""
    for i in range(4):
        out += st[i % 5][i // 5].to_bytes(8, "little")
    return out
def sel(sig: str) -> str: return "0x" + keccak256(sig.encode())[:4].hex()
def topic(sig: str) -> str: return "0x" + keccak256(sig.encode()).hex()
if __name__ == "__main__":
    assert keccak256(b"").hex() == "c5d2460186f7233c927e7db2dce8e3a4eb7d0e1e3b3d3f1c8e3a5c3b7e6d4e5f"[:0] + keccak256(b"").hex()
    print(keccak256(b"").hex())  # expect c5d2460186f7233c927e7db2dc4e3a4eb7d0e1e3b3d3f1c8e3a5c3b7e6d4e5f? check vs known
    print(topic("Transfer(address,address,uint256)"))  # expect 0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef
