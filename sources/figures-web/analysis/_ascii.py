"""ASCII 'look' at legend keys and plot corners - the substitute for eyeballing.

Prints a compact, downsampled ASCII view of small crops of the PDF chart so the
line style of every legend key can be read off the vector artwork.
"""
import fitz
import numpy as np

doc = fitz.open("Science-A-New-Golden-Age.pdf")
CHARS = " .:-=+*#%@"

KEYS = [
    ("p24 key Higher Education", 24, (126.4, 480.8, 150.0, 487.0)),
    ("p24 key Business",         24, (248.3, 480.3, 271.0, 487.0)),
    ("p24 key Federal",          24, (330.1, 480.8, 353.4, 487.0)),
    ("p24 key Nonprofits",       24, (407.4, 480.8, 430.4, 487.0)),
    ("p27 key United States",    27, (177.3, 541.8, 200.8, 548.0)),
    ("p27 key EU 27",            27, (299.4, 541.0, 322.1, 547.2)),
    ("p27 key China",            27, (381.1, 541.8, 404.3, 548.0)),
    ("p29 key Natural Sci & Eng", 29, (217.1, 500.2, 240.6, 506.4)),
    ("p29 key Social & Applied", 29, (217.6, 511.6, 240.9, 517.8)),
    ("p34 key MD-PhD",           34, (195.7, 493.8, 219.2, 500.0)),
    ("p34 key PhD only",         34, (270.9, 493.1, 293.7, 499.3)),
    ("p34 key MD only",          34, (355.6, 493.8, 378.9, 500.0)),
]


def show(label, pno, box, cols=72, rows=9):
    p = doc[pno - 1]
    pix = p.get_pixmap(matrix=fitz.Matrix(8, 8), clip=fitz.Rect(*box), colorspace=fitz.csGRAY)
    a = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width).astype(float)
    # downsample by block-min so thin line work survives
    H, W = a.shape
    out = []
    for r in range(rows):
        line = ""
        for c in range(cols):
            y0 = int(r * H / rows); y1 = max(y0 + 1, int((r + 1) * H / rows))
            x0 = int(c * W / cols); x1 = max(x0 + 1, int((c + 1) * W / cols))
            v = a[y0:y1, x0:x1].min()
            line += CHARS[min(9, int((255 - v) // 26))]
        out.append(line.rstrip())
    ink = [l for l in out if l.strip()]
    print("%-26s | box=(%.0f,%.0f,%.0f,%.0f)" % (label, box[0], box[1], box[2], box[3]))
    for l in ink:
        print("    |" + l)
    if not ink:
        print("    |(blank)")


for label, pno, box in KEYS:
    show(label, pno, box)