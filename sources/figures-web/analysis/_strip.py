"""Segment the thin web strip graph-1-2.png into glyphs and print them for reading."""
import numpy as np
from PIL import Image

CH = " .:-=+*#%@"
im = Image.open("sources/figures-web/raw-graph-1-2.png").convert("RGBA")
bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
a = np.array(Image.alpha_composite(bg, im).convert("L")).astype(float)
ink = a < 170
colink = ink.sum(axis=0)
# find word groups (gaps wider than 6px = word break)
segs = []
inrun = False
for i, v in enumerate(colink):
    if v > 0 and not inrun:
        start = i; inrun = True
    elif v == 0 and inrun:
        segs.append((start, i)); inrun = False
if inrun:
    segs.append((start, len(colink)))
print("total glyph segments:", len(segs))
# merge glyphs into words separated by >= 5 px
words = []
cur = [segs[0]]
for s in segs[1:]:
    if s[0] - cur[-1][1] >= 5:
        words.append((cur[0][0], cur[-1][1]))
        cur = [s]
    else:
        cur.append(s)
words.append((cur[0][0], cur[-1][1]))
print("words:", len(words))
for wi, (x0, x1) in enumerate(words[:14]):
    sub = a[:, x0:x1]
    ys = np.where((sub < 170).any(axis=1))[0]
    y0, y1 = ys.min(), ys.max() + 1
    g = sub[y0:y1]
    h, w = g.shape
    # scale to ~10 rows tall
    scale = max(1, int(round(10.0 / h)))
    big = np.array(Image.fromarray(np.clip(g, 0, 255).astype(np.uint8)).resize((w * scale, h * scale), Image.LANCZOS)).astype(float)
    print("--- word %d  x=%d..%d  w=%d h=%d" % (wi, x0, x1, w, h))
    for r in big:
        print("   " + "".join(CH[min(9, int((255 - v) // 26))] for v in r))