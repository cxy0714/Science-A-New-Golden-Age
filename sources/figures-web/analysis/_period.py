"""Compare dash period (mark+gap) of legend keys with that of plotted series."""
import fitz
import numpy as np

doc = fitz.open("Science-A-New-Golden-Age.pdf")

key_periods = {  # mark+gap in pt, measured from rendered legend keys
    "solid(1 mark)": None,
    "fine_dot": 0.77,
    "short_dash": 2.08,
    "long_dash": 5.36,
}

FIGS = [
    ("fig1 left", 24, (128, 244, 295, 445)),
    ("fig1 right", 24, (317, 244, 484, 445)),
    ("fig2", 27, (128, 283, 488, 500)),
    ("fig3", 29, (128, 251, 488, 472)),
    ("fig4", 34, (128, 240, 488, 462)),
]

for name, pno, plot in FIGS:
    p = doc[pno - 1]
    print("=== %s" % name)
    for d in sorted(p.get_drawings(), key=lambda d: -len(d["items"])):
        r = d["rect"]
        n = len(d["items"])
        if n < 10 or r.width < 100:
            continue
        px0, py0, px1, py1 = plot
        if not (r.x0 >= px0 - 6 and r.x1 <= px1 + 6 and r.y0 >= py0 - 12 and r.y1 <= py1 + 25):
            continue
        starts = np.array([[it[1].x, it[1].y] for it in d["items"] if it[0] == "l"])
        if len(starts) < 3:
            continue
        # distance along x between consecutive dash starts
        dx = np.diff(starts[:, 0])
        dx = dx[dx > 0.01] if len(dx) else np.array([])
        seg = np.array([((it[1].x - it[2].x) ** 2 + (it[1].y - it[2].y) ** 2) ** 0.5
                        for it in d["items"] if it[0] == "l"])
        print("   w=%-5s n=%-4d mark_med=%.2f  start_dx_med=%.2f" %
              (round(d.get("width") or 0, 3), n, float(np.median(seg)),
               float(np.median(dx)) if len(dx) else -1))