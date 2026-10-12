"""Shape-match web PNG figures against PDF chart regions (plot area only).

The plot interior carries the data ink; comparing interiors after normalising to
the detected plot frame cancels out differences in margins, fonts and legends.
"""
import fitz
import numpy as np
from PIL import Image

PDF = "Science-A-New-Golden-Age.pdf"


def pdf_gray(pno, box, Z=3.0):
    doc = fitz.open(PDF)
    p = doc[pno - 1]
    pix = p.get_pixmap(matrix=fitz.Matrix(Z, Z), clip=fitz.Rect(*box), colorspace=fitz.csGRAY)
    return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width).astype(int)


def web_gray(f):
    im = Image.open(f).convert("RGBA")
    bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
    return np.array(Image.alpha_composite(bg, im).convert("L")).astype(int)


def find_frame(a, thr=200, fw=0.5, fh=0.5):
    m = a < thr
    H, W = m.shape
    rows = np.where(m.sum(axis=1) > fw * W)[0]
    cols = np.where(m.sum(axis=0) > fh * H)[0]
    if len(rows) == 0 or len(cols) == 0:
        return None
    return int(cols.min()), int(rows.min()), int(cols.max()) + 1, int(rows.max()) + 1


def interior(a, box, W=400, H=260):
    x0, y0, x1, y1 = box
    # inset to drop the frame stroke itself
    ins = max(2, (y1 - y0) // 100, (x1 - x0) // 100)
    sub = a[y0 + ins:y1 - ins, x0 + ins:x1 - ins]
    im = Image.fromarray(np.clip(sub, 0, 255).astype(np.uint8)).resize((W, H), Image.BILINEAR)
    return np.array(im).astype(float)


def corr(A, B):
    a = A - A.mean()
    b = B - B.mean()
    d = np.sqrt((a * a).sum() * (b * b).sum())
    return float((a * b).sum() / d) if d else float("nan")


PDF_C = {
    "pdf-f1-left":  (24, (88, 208, 306, 500)),
    "pdf-f1-right": (24, (306, 208, 500, 500)),
    "pdf-f2":       (27, (80, 272, 495, 560)),
    "pdf-f3":       (29, (80, 242, 495, 528)),
    "pdf-f4":       (34, (80, 228, 495, 512)),
}
WEB = {
    "web-1-1": "sources/figures-web/raw-graph-1-1.png",
    "web-1-2": "sources/figures-web/raw-graph-1-2.png",
    "web-1-3": "sources/figures-web/raw-graph-1-3.png",
    "web-1-4": "sources/figures-web/raw-graph-1-4.png",
    "web-2-1": "sources/figures-web/raw-graph-2-1.png",
}

pdf_int = {}
for k, (pno, box) in PDF_C.items():
    a = pdf_gray(pno, box)
    fr = find_frame(a)
    pdf_int[k] = interior(a, fr) if fr else None
    print("%-13s frame=%s aspect=%.3f" % (k, fr, (fr[2] - fr[0]) / (fr[3] - fr[1])))

print()
for k, path in WEB.items():
    a = web_gray(path)
    fr = find_frame(a)
    if not fr:
        print("%-9s NO FRAME" % k)
        continue
    ar = (fr[2] - fr[0]) / (fr[3] - fr[1])
    print("%-9s frame=%s aspect=%.3f" % (k, fr, ar))
    if ar > 1.3 and fr[2] - fr[0] > 300:
        # possibly two panels side by side -> split at the widest interior gap
        m = a < 200
        colink = m[fr[1]:fr[3], fr[0]:fr[2]].sum(axis=0)
        half = (fr[2] - fr[0]) // 2
        for label, wbox in [("whole", fr),
                            ("left-half", (fr[0], fr[1], fr[0] + half, fr[3])),
                            ("right-half", (fr[0] + half, fr[1], fr[2], fr[3]))]:
            I = interior(a, wbox)
            best = sorted(((corr(I, v), nk) for nk, v in pdf_int.items() if v is not None), reverse=True)[:2]
            print("      %-11s best: %s" % (label, ", ".join("%s=%.3f" % (n, c) for c, n in best)))
    else:
        I = interior(a, fr)
        best = sorted(((corr(I, v), nk) for nk, v in pdf_int.items() if v is not None), reverse=True)[:3]
        print("      best: %s" % ", ".join("%s=%.3f" % (n, c) for c, n in best))