#!/usr/bin/env python3
"""Report structural elements per extracted part (captions, stat callouts, tables) and
list images referenced by the official web edition."""
from __future__ import annotations

import pathlib
import re

from bs4 import BeautifulSoup

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "tools" / "_structure.txt"


def main() -> None:
    lines: list[str] = ["== extracted parts =="]
    for path in sorted((ROOT / "sources" / "en").glob("*.en.md")):
        text = path.read_text(encoding="utf-8")
        captions = [l.strip() for l in text.splitlines() if re.fullmatch(r"\*[^*].*\*", l.strip())]
        stats = [l.strip() for l in text.splitlines() if l.strip().startswith(">")]
        table = [l.strip() for l in text.splitlines() if l.strip().startswith("|")]
        subheads = [l.strip() for l in text.splitlines() if re.fullmatch(r"\*\*[^*]+\*\*", l.strip())]
        lines.append(f"\n--- {path.name}: captions={len(captions)} stat={len(stats)} "
                     f"table_lines={len(table)} subheads={len(subheads)}")
        for item in captions:
            lines.append(f"  caption: {item[:110]}")
        for item in stats:
            lines.append(f"  stat: {item[:110]}")
        for item in table[:6]:
            lines.append(f"  table: {item[:110]}")
    soup = BeautifulSoup((ROOT / "sources" / "whitehouse-science.html").read_text(encoding="utf-8"), "html.parser")
    lines.append("\n== <img> in web edition ==")
    for img in soup.find_all("img"):
        lines.append(f"  src={img.get('src')} alt={img.get('alt')!r} class={img.get('class')} "
                     f"width={img.get('width')} height={img.get('height')}")
        parent = img.find_parent(["figure", "div", "p"])
        if parent is not None:
            lines.append(f"     parent: <{parent.name} class={' '.join(parent.get('class') or [])}>"
                         f" text={parent.get_text(' ', strip=True)[:110]!r}")
    lines.append("\n== <figure>/<figcaption> in web edition ==")
    for fig in soup.find_all("figure"):
        lines.append(f"  figure class={fig.get('class')} text={fig.get_text(' ', strip=True)[:140]!r}")
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()