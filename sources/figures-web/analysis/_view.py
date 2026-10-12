"""ASCII 'viewer' for raster figures - downsample and print an ink map."""
import sys
import numpy as np
from PIL import Image

CH = " .:-=+*#%@"


def load(path):
    im = Image.open(path).convert("RGBA")
    bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
    return np.array(Image.alpha_composite(bg, im).convert("L")).astype(float)


def view(path, cols=170, row_scale=2.1):
    a = load(path)
    H, W = a.shape
    rows = max(1, int(cols * H / W / row_scale))
    out = []
    for r in range(rows):
        y0 = int(r * H / rows); y1 = max(y0 + 1, int((r + 1) * H / rows))
        line = ""
        for c in range(cols):
            x0 = int(c * W / cols); x1 = max(x0 + 1, int((c + 1) * W / cols))
            v = a[y0:y1, x0:x1].min()
            line += CH[min(9, int((255 - v) // 26))]
        out.append(line.rstrip())
    print("### %s  (%dx%d) -> %d cols" % (path, W, H, cols))
    for l in out:
        print(l)


if __name__ == "__main__":
    for p in sys.argv[1:]:
        view(p)