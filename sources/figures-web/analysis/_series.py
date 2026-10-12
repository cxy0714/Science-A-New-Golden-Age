"""Series-shape probe: recover data ranges from the vector paths of each chart.

Runs against the allowed cache directory only.
"""
import fitz
import numpy as np

doc = fitz.open("Science-A-New-Golden-Age.pdf")

# figure -> (page, plot-ish rect, y-value at top tick, y-coord of that tick,
#            y-value at bottom tick, y-coord of that tick, label)
FIGS = {
    "fig1-left":  (24, (128, 244, 295, 445), 60, 246.7, 0, 441.3),
    "fig1-right": (24, (317, 244, 484, 445), 60, 246.7, 0, 441.3),
    "fig2":       (27, (128, 283, 488, 500), 1200, 303.1, 0, 497.7),
    "fig3":       (29, (128, 251, 488, 472), 50, 271.1, 0, 466.2),
    "fig4":       (34, (128, 240, 488, 462), 46, 260.8, 34, 455.4),
}


def value(y, vtop, ytop, vbot, ybot):
    return vbot + (y - ybot) * (vtop - vbot) / (ytop - ybot)


for name, (pno, plot, vtop, ytop, vbot, ybot) in FIGS.items():
    p = doc[pno - 1]
    print("=== %s (pdf page %d)" % (name, pno))
    for d in sorted(p.get_drawings(), key=lambda d: -len(d["items"])):
        r = d["rect"]
        n = len(d["items"])
        if n < 10 or r.width < 100:
            continue
        px0, py0, px1, py1 = plot
        if not (r.x0 >= px0 - 6 and r.x1 <= px1 + 6 and r.y0 >= py0 - 12 and r.y1 <= py1 + 25):
            continue
        pts = [(it[1].x, it[1].y) for it in d["items"] if it[0] == "l"]
        pts += [(it[2].x, it[2].y) for it in d["items"] if it[0] == "l"]
        xs = sorted({round(x, 2) for x, _ in pts})
        ys = [y for _, y in pts]
        lo = value(max(ys), vtop, ytop, vbot, ybot)
        hi = value(min(ys), vtop, ytop, vbot, ybot)
        print("   w=%-5s items=%-4d distinct_x=%-3d x=[%.1f..%.1f] value range = %.0f .. %.0f"
              % (round(d.get("width") or 0, 3), n, len(xs), min(xs), max(xs), lo, hi))