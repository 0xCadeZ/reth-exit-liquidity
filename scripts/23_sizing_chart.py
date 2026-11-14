"""Two panels: (1) monthly ETH reaching the buffer against estimated exit demand; (2) share of days every exit could be
paid, by buffer target, as it happened (cap only) and pre-filled, with yield cost. Writes charts/2_sizing.svg/.html."""
import json, os
R = os.path.join(os.path.dirname(__file__), ".."); S = json.load(open(os.path.join(R, "sizing", "results.json"))); C = os.path.join(R, "charts")
BLUE, ORANGE, AQUA, MUTED, INK, INK2, GRID = "#2a78d6", "#eb6834", "#1baf7a", "#898781", "#0b0b0b", "#52514e", "#e1e0d9"
FONT = "font-family:system-ui,-apple-system,'Segoe UI',sans-serif"
W = 760; L = 60; Rm = 40; PW = W - L - Rm
o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} 560" width="{W}" height="560" style="{FONT}" role="img" aria-label="Buffer inflow against exit demand by month, and days with every exit paid by buffer target">', f'<rect width="{W}" height="560" fill="#fcfcfb"/>']
# panel 1
months = list(S["monthly_inflow_eth"]); nm = {"05": "May", "06": "Jun", "07": "Jul", "08": "Aug", "09": "Sep", "10": "Oct", "11": "Nov 1-12"}
T1, H1 = 40, 170; YMAX = 20000
y1 = lambda v: T1 + H1 * (1 - min(v, YMAX) / YMAX)
o.append(f'<text x="{L}" y="{T1 - 16}" font-size="12.5" font-weight="600" fill="{INK}">ETH reaching the buffer against estimated exit demand, by month</text>')
for v in (0, 5000, 10000, 15000, 20000):
    o.append(f'<line x1="{L}" x2="{W - Rm}" y1="{y1(v):.1f}" y2="{y1(v):.1f}" stroke="{INK2 if v == 0 else GRID}"/><text x="{L - 8}" y="{y1(v) + 4:.1f}" font-size="11" fill="{INK2}" text-anchor="end">{v // 1000}k</text>')
gw = PW / len(months); bw = gw * 0.32
for i, m in enumerate(months):
    x0 = L + i * gw + gw / 2; vi = S["monthly_inflow_eth"][m]; vd = S["monthly_S2_demand_mean_eth"][m]
    o.append(f'<rect x="{x0 - bw - 1:.1f}" y="{y1(vi):.1f}" width="{bw:.1f}" height="{T1 + H1 - y1(vi):.1f}" fill="{BLUE}"/>')
    o.append(f'<rect x="{x0 + 1:.1f}" y="{y1(vd):.1f}" width="{bw:.1f}" height="{T1 + H1 - y1(vd):.1f}" fill="{ORANGE}"/>')
    if vi > YMAX: o.append(f'<text x="{x0 - bw / 2:.1f}" y="{T1 + 12}" font-size="10.5" fill="{INK}" text-anchor="middle">{vi / 1000:.0f}k</text>')
    o.append(f'<text x="{x0:.1f}" y="{T1 + H1 + 16}" font-size="11" fill="{INK2}" text-anchor="middle">{nm[m[5:]]}</text>')
o.append(f'<rect x="{L}" y="{T1 + H1 + 26}" width="10" height="10" fill="{BLUE}"/><text x="{L + 15}" y="{T1 + H1 + 35}" font-size="11" fill="{INK2}">ETH in (node payouts, recycled deposits, mints)</text>')
o.append(f'<rect x="{L + 290}" y="{T1 + H1 + 26}" width="10" height="10" fill="{ORANGE}"/><text x="{L + 305}" y="{T1 + H1 + 35}" font-size="11" fill="{INK2}">Exit demand, empty days at funded-day burn rates (average of runs)</text>')
# panel 2
T2, H2 = 330, 170; xs = [0.01, 0.02, 0.03, 0.05, 0.07, 0.10]
x2 = lambda t: L + PW * (xs.index(t)) / (len(xs) - 1)
y2 = lambda v: T2 + H2 * (1 - (v - 0.5) / 0.5)
o.append(f'<text x="{L}" y="{T2 - 26}" font-size="12.5" font-weight="600" fill="{INK}">Share of days every exit could be paid, by buffer target</text>')
for v in (0.5, 0.6, 0.7, 0.8, 0.9, 1.0):
    o.append(f'<line x1="{L}" x2="{W - Rm}" y1="{y2(v):.1f}" y2="{y2(v):.1f}" stroke="{GRID}"/><text x="{L - 8}" y="{y2(v) + 4:.1f}" font-size="11" fill="{INK2}" text-anchor="end">{v:.0%}</text>')
cap = [S["curve"][str(t)]["S2_median"] if str(t) in S["curve"] else S["curve"][str(t).rstrip("0")]["S2_median"] for t in (0.01, 0.02, 0.03, 0.05)] + [None, None]
pre = [S["prefilled_S2"][str(t)]["days_paid_median"] for t in xs]
pts = " ".join(f"{x2(t):.1f},{y2(v):.1f}" for t, v in zip(xs, cap) if v is not None)
o.append(f'<polyline points="{pts}" fill="none" stroke="{MUTED}" stroke-width="2" stroke-dasharray="5 4"/>')
o.append(f'<polyline points="{" ".join(f"{x2(t):.1f},{y2(v):.1f}" for t, v in zip(xs, pre))}" fill="none" stroke="{AQUA}" stroke-width="2.4"/>')
for t, v in zip(xs, pre):
    o.append(f'<circle cx="{x2(t):.1f}" cy="{y2(v):.1f}" r="3.5" fill="{AQUA}"/>')
    c = S["prefilled_S2"][str(t)]["cost_if_always_full_bps_yr"]
    o.append(f'<text x="{x2(t):.1f}" y="{T2 + H2 + 16}" font-size="11" fill="{INK2}" text-anchor="middle">{t:.0%}</text><text x="{x2(t):.1f}" y="{T2 + H2 + 30}" font-size="10.5" fill="{MUTED}" text-anchor="middle">{c:.0f} bps/yr</text>')
o.append(f'<text x="{L}" y="{T2 + H2 + 48}" font-size="11" fill="{INK2}">Target as a share of rETH value; below it, the yield rETH holders would give up if the buffer stayed full.</text>')
o.append(f'<line x1="{L}" x2="{L + 22}" y1="{T2 - 10}" y2="{T2 - 10}" stroke="{AQUA}" stroke-width="2.4"/><text x="{L + 28}" y="{T2 - 6}" font-size="11" fill="{INK2}">Buffer full on May 1</text>')
o.append(f'<line x1="{L + 170}" x2="{L + 192}" y1="{T2 - 10}" y2="{T2 - 10}" stroke="{MUTED}" stroke-width="2" stroke-dasharray="5 4"/><text x="{L + 198}" y="{T2 - 6}" font-size="11" fill="{INK2}">Higher target only, filled by flows as they happened (flat: nothing to fill it)</text>')
o.append("</svg>"); svg = "\n".join(o)
open(os.path.join(C, "2_sizing.svg"), "w").write(svg)
open(os.path.join(C, "2_sizing.html"), "w").write(f'<!doctype html><html><head><meta charset="utf-8"><title>Buffer sizing</title></head><body style="margin:0;background:#fcfcfb">{svg}</body></html>')
print("ok")
