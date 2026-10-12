"""Quantitative dash-pattern matching between legend keys and plotted series."""
import fitz
import numpy as np

doc = fitz.open("Science-A-New-Golden-Age.pdf")

KEYS = [
    ("fig1 Higher Education", 24, (126.4, 483.80, 150.0, 483.85)),
    ("fig1 Business",         24, (248.3, 483.80, 271.0, 483.85)),
    ("fig1 Federal",          24, (330.1, 483.80, 353.4, 483.85)),
    ("fig1 Nonprofits",       24, (407.4, 483.80, 430.4, 483.85)),
    ("fig2 United States",    27, (177.3, 544.80, 200.8, 544.85)),
    ("fig2 EU 27",            27, (299.4, 544.00, 322.1, 544.05)),
    ("fig2 China",            27, (381.1, 544.80, 404.3, 544.85)),
    ("fig3 Natural Sci&Eng",  29, (217.1, 503.20, 240.6, 503.25)),
    ("fig3 Social&Applied",   29, (217.6, 514.60, 240.9, 514.65)),
    ("fig4 MD-PhD",           34, (195.7, 496.80, 219.2, 496.85)),
    ("fig4 PhD only",         34, (270.9, 496.10, 293.7, 496.15)),
    ("fig4 MD only",          34, (355.6, 496.80, 378.9, 496.85)),
]


def runs(label, pno, box):
    p = doc[pno - 1]
    pad = 1.0
    b = fitz.Rect(box[0] - pad, box[1] - pad, box[2] + pad, box[3] + pad)
    Z = 24.0
    pix = p.get_pixmap(matrix=fitz.Matrix(Z, Z), clip=b, colorspace=fitz.csGRAY)
    a = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
    col = a.min(axis=0)  # darkest value per column
    ink = col < 200
    # run-length encode
    out = []
    cur = ink[0]
    n = 1
    for v in ink[1:]:
        if v == cur:
            n += 1
        else:
            out.append((bool(cur), round(n / Z, 2)))
            cur = v
            n = 1
    out.append((bool(cur), round(n / Z, 2)))
    # drop leading/trailing whitespace runs
    while out and not out[0][0]:
        out.pop(0)
    while out and not out[-1][0]:
        out.pop()
    marks = [d for f, d in out if f]
    gaps = [d for f, d in out if not f]
    print("%-24s marks=%-2d mark_len med=%.2f min=%.2f max=%.2f | gap med=%.2f"
          % (label, len(marks), float(np.median(marks)) if marks else -1,
             min(marks) if marks else -1, max(marks) if marks else -1,
             float(np.median(gaps)) if gaps else 0.0))


print("LEGEND KEYS (mark lengths in PDF points)")
for lab, pno, box in KEYS:
    runs(lab, pno, box)

print()
print("PLOTTED SERIES (polyline segment lengths in PDF points)")
FIGS = [
    ("fig1 left", 24, (128, 244, 295, 445)),
    ("fig1 right", 24, (317, 244, 484, 445)),
    ("fig2", 27, (128, 283, 488, 500)),
    ("fig3", 29, (128, 251, 488, 472)),
    ("fig4", 34, (128, 240, 488, 462)),
]
for name, pno, plot in FIGS:
    p = doc[pno - 1]
    for d in sorted(p.get_drawings(), key=lambda d: -len(d["items"])):
        r = d["rect"]
        n = len(d["items"])
        if n < 10 or r.width < 100:
            continue
        px0, py0, px1, py1 = plot
        if not (r.x0 >= px0 - 6 and r.x1 <= px1 + 6 and r.y0 >= py0 - 12 and r.y1 <= py1 + 25):
            continue
        segs = []
        for it in d["items"]:
            if it[0] == "l":
                segs.append(((it[1].x - it[2].x) ** 2 + (it[1].y - it[2].y) ** 2) ** 0.5)
        segs = np.array(segs)
        print("%-11s w=%-5s items=%-4d seg_len med=%.2f p90=%.2f max=%.2f  n_short(<1pt)=%d"
              % (name, round(d.get("width") or 0, 3), n, float(np.median(segs)),
                 float(np.percentile(segs, 90)), float(segs.max()), int((segs < 1).sum())))