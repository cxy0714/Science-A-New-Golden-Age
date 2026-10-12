"""Per-glyph ASCII dump of the first words of the graph-1-2 strip."""
import numpy as np
from PIL import Image

CH = " .:-=+*#%@"
im = Image.open("sources/figures-web/raw-graph-1-2.png").convert("RGBA")
bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
a = np.array(Image.alpha_composite(bg, im).convert("L")).astype(float)
ink = a < 170

WINDOWS = [(95, 210), (185, 210), (220, 335), (330, 350), (348, 390), (400, 545), (480, 545)]

for (x0, x1) in WINDOWS:
    sub = a[:, x0:x1]
    m = sub < 170
    ys = np.where(m.any(axis=1))[0]
    if len(ys) == 0:
        continue
    sub = sub[ys.min():ys.max() + 1]
    h, w = sub.shape
    s = max(1, int(round(16.0 / h)))
    big = np.array(Image.fromarray(np.clip(sub, 0, 255).astype(np.uint8))
                   .resize((w * s, h * s), Image.LANCZOS)).astype(float)
    # glyph segmentation inside the window
    cols = (big < 170).sum(axis=0)
    glyphs = []
    run = None
    for i, v in enumerate(cols):
        if v > 0 and run is None:
            run = i
        elif v == 0 and run is not None:
            glyphs.append((run, i)); run = None
    if run is not None:
        glyphs.append((run, len(cols)))
    print("=== window x=%d..%d  height=%d -> %d glyph runs" % (x0, x1, h, len(glyphs)))
    for gi, (g0, g1) in enumerate(glyphs):
        g = big[:, g0:g1]
        print("  glyph %d (w=%d)" % (gi, g1 - g0))
        for r in g:
            print("    " + "".join(CH[min(9, int((255 - v) // 26))] for v in r))