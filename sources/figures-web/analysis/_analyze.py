"""Scratch analysis helpers for figure identification (not a deliverable).

Lives in sources/figures-web/ (the allowed cache directory).
"""
import numpy as np
import fitz
from PIL import Image

PDF = "Science-A-New-Golden-Age.pdf"


def pdf_gray(pno, box, Z=3.0):
    doc = fitz.open(PDF)
    p = doc[pno - 1]
    pix = p.get_pixmap(matrix=fitz.Matrix(Z, Z), clip=fitz.Rect(*box), colorspace=fitz.csGRAY)
    a = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width).astype(int)
    return a


def gray_of_web(f):
    im = Image.open(f).convert("RGBA")
    bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
    return np.array(Image.alpha_composite(bg, im).convert("L")).astype(int)


def ink_bbox(a, thr=200):
    m = a < thr
    ys, xs = np.where(m)
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def legend_swatches(pno, ylo, yhi):
    """Return short line segments (legend keys) in a horizontal band."""
    doc = fitz.open(PDF)
    p = doc[pno - 1]
    out = []
    for d in p.get_drawings():
        r = d["rect"]
        if ylo <= (r.y0 + r.y1) / 2 <= yhi and r.width < 60 and r.height < 12:
            out.append((round(r.x0, 2), round(r.y0, 2), round(r.x1, 2), round(r.y1, 2), len(d["items"]), round(d.get("width") or 0, 3)))
    return sorted(out)


def legend_labels(pno, ylo, yhi, xlo=0):
    doc = fitz.open(PDF)
    p = doc[pno - 1]
    out = []
    for b in p.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                bb = s["bbox"]
                if ylo <= (bb[1] + bb[3]) / 2 <= yhi and bb[0] >= xlo:
                    out.append((round(bb[0], 1), round(bb[1], 1), s["text"]))
    return sorted(out)


def swatch_gray(pno, x0, x1, y, box):
    """Mean gray of the darkest pixels along a legend swatch segment."""
    # convert pdf coords -> local crop pixels
    Z = 8.0
    a = pdf_gray(pno, box, Z)
    px0 = int((x0 - box[0]) * Z)
    px1 = int((x1 - box[0]) * Z)
    py = int((y - box[1]) * Z)
    band = a[max(0, py - 8):py + 9, max(0, px0):px1 + 1]
    if band.size == 0:
        return None
    vals = band.flatten()
    vals = vals[vals < 220]
    return (int(vals.min()), int(np.median(vals)), len(vals)) if len(vals) else None