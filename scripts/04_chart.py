"""One chart: DEX price of rETH against the protocol rate (top) and rETH minted per day (bottom), days with empty burn collateral shaded.
Light theme, same palette as the Uniswap burn-flow charts. Writes charts/1_premium_vs_mints.svg and .html."""
import csv, os
D = os.path.join(os.path.dirname(__file__), "..", "data"); C = os.path.join(os.path.dirname(__file__), "..", "charts"); os.makedirs(C, exist_ok=True)
BLUE, ORANGE, MUTED, INK, INK2, GRID, SHADE = "#2a78d6", "#eb6834", "#898781", "#0b0b0b", "#52514e", "#e1e0d9", "#f3e9e2"
FONT = "font-family:system-ui,-apple-system,'Segoe UI',sans-serif"
rows = list(csv.DictReader(open(os.path.join(D, "daily.csv"))))[:-1]
n = len(rows); prem = [float(r["prem_bps"]) for r in rows]; mint = [float(r["mint_reth"]) for r in rows]; emp = [float(r["collateral_eth"]) < 100 for r in rows]
W, L, Rm = 760, 56, 16; PW = W - L - Rm
T1, H1 = 30, 170; T2, H2 = T1 + H1 + 48, 150; H = T2 + H2 + 52
x = lambda i: L + PW * i / (n - 1); bw = PW / n
LO, HI = -60, 20
y1 = lambda v: T1 + H1 * (HI - max(LO, min(HI, v))) / (HI - LO)
MMAX = 400
y2 = lambda v: T2 + H2 * (1 - min(v, MMAX) / MMAX)
o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" style="{FONT}" role="img" aria-label="rETH DEX price against protocol rate and daily mints, May to November 2026">',
     f'<rect width="{W}" height="{H}" fill="#fcfcfb"/>']
# shaded spans
i = 0
while i < n:
    if emp[i]:
        j = i
        while j + 1 < n and emp[j + 1]: j += 1
        for (t, h) in ((T1, H1), (T2, H2)):
            o.append(f'<rect x="{x(i) - bw / 2:.1f}" y="{t}" width="{(j - i + 1) * bw:.1f}" height="{h}" fill="{SHADE}"/>')
        i = j + 1
    else: i += 1
# panel 1 grid + axis
o.append(f'<text x="{L}" y="{T1 - 12}" font-size="12" font-weight="600" fill="{INK}">DEX price of rETH against the protocol rate, basis points (daily, volume-weighted)</text>')
for v in (20, 5, 0, -20, -40, -60):
    o.append(f'<line x1="{L}" x2="{W - Rm}" y1="{y1(v):.1f}" y2="{y1(v):.1f}" stroke="{INK2 if v == 0 else GRID}" stroke-width="{1 if v == 0 else 1}" {"" if v != 5 else "stroke-dasharray=\"4 3\""}/>')
    o.append(f'<text x="{L - 8}" y="{y1(v) + 4:.1f}" font-size="11" fill="{INK2}" text-anchor="end">{v:+d}</text>' if v else f'<text x="{L - 8}" y="{y1(v) + 4:.1f}" font-size="11" fill="{INK2}" text-anchor="end">0</text>')
pts = " ".join(f"{x(i):.1f},{y1(v):.1f}" for i, v in enumerate(prem))
o.append(f'<polyline points="{pts}" fill="none" stroke="{BLUE}" stroke-width="1.8" stroke-linejoin="round"/>')
for i, v in enumerate(prem):   # mark clipped days
    if v < LO: o.append(f'<path d="M{x(i) - 3.5:.1f},{T1 + H1 - 7} l3.5,6 l3.5,-6 z" fill="{BLUE}"/>')
    if v > HI: o.append(f'<path d="M{x(i) - 3.5:.1f},{T1 + 7} l3.5,-6 l3.5,6 z" fill="{BLUE}"/>')
# panel 2
o.append(f'<text x="{L}" y="{T2 - 12}" font-size="12" font-weight="600" fill="{INK}">rETH minted per day</text>')
for v in (0, 100, 200, 300, 400):
    o.append(f'<line x1="{L}" x2="{W - Rm}" y1="{y2(v):.1f}" y2="{y2(v):.1f}" stroke="{INK2 if v == 0 else GRID}"/>')
    o.append(f'<text x="{L - 8}" y="{y2(v) + 4:.1f}" font-size="11" fill="{INK2}" text-anchor="end">{v}</text>')
for i, v in enumerate(mint):
    if v > 0.5:
        o.append(f'<rect x="{x(i) - bw * 0.36:.1f}" y="{y2(v):.1f}" width="{bw * 0.72:.1f}" height="{T2 + H2 - y2(v):.1f}" fill="{ORANGE}"/>')
    if v > MMAX: o.append(f'<path d="M{x(i) - 3.5:.1f},{T2 - 1} l3.5,-6 l3.5,6 z" fill="{ORANGE}"/>')
# x axis months
for i, r in enumerate(rows):
    if r["date"].endswith("-01"):
        nm = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][int(r["date"][5:7])]
        for t, h in ((T1, H1), (T2, H2)): o.append(f'<line x1="{x(i):.1f}" x2="{x(i):.1f}" y1="{t + h}" y2="{t + h + 4}" stroke="{INK2}"/>')
        o.append(f'<text x="{x(i) + 3:.1f}" y="{T2 + H2 + 17}" font-size="11" fill="{INK2}">{nm}</text>')
        o.append(f'<text x="{x(i) + 3:.1f}" y="{T1 + H1 + 15}" font-size="11" fill="{INK2}">{nm}</text>')
# legend for the shade
o.append(f'<rect x="{L}" y="{H - 31}" width="12" height="10" fill="{SHADE}" stroke="{GRID}"/><text x="{L + 18}" y="{H - 22}" font-size="11" fill="{INK2}">Shaded: under 100 ETH in the rETH contract to pay burns at the start of the day. Triangles: value off the scale.</text>')
o.append(f'<text x="{L}" y="{H - 6}" font-size="11" fill="{INK2}">Top panel: 0 is the protocol rate, which is what a burn pays. The dashed line at +5 is the cost to mint (0.05% deposit fee).</text>')
o.append("</svg>")
svg = "\n".join(o)
open(os.path.join(C, "1_premium_vs_mints.svg"), "w").write(svg)
html = f'''<!doctype html><html><head><meta charset="utf-8"><style>body{{margin:0;background:#fcfcfb;{FONT};color:{INK}}}
.c{{width:{W}px;padding:20px 24px 16px;box-sizing:border-box}} h2{{font-size:17px;margin:0 0 2px;font-weight:600}} p{{margin:0 0 12px;color:{INK2};font-size:13px}}
.src{{color:{MUTED};font-size:11px;margin-top:8px}}</style></head><body><div class="c"><h2>When the rETH contract cannot pay burns, rETH trades below the rate and minting stops</h2>
<p>Ethereum mainnet, 2026-05-01 to 2026-11-12. Uniswap v3 0.01% and v4 rETH/ETH pools.</p>{svg}
<div class="src">Source: Ethereum mainnet event logs and contract state from public RPC. Code and data: research/reth-mint.</div></div></body></html>'''
open(os.path.join(C, "1_premium_vs_mints.html"), "w").write(html)
print("ok", n)
