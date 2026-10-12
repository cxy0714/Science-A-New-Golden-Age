#!/usr/bin/env python3
"""Count block kinds per part and compare with what the EPUB contains.

A quick accountability check: how many paragraphs/captions/stats/headings in the
sources, and how many blockquotes/figures/asides/headings in the built documents.
"""
from __future__ import annotations

import pathlib
import sys
import zipfile
from collections import Counter
from xml.etree import ElementTree

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from build_bilingual import PARTS, parse_blocks  # noqa: E402

XHTML = "{http://www.w3.org/1999/xhtml}"


def main() -> None:
    epub = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "科学_一个新的黄金时代_中英对照.epub"
    source: Counter[str] = Counter()
    for part in PARTS:
        if part["slug"] == "references":
            continue
        path = ROOT / "sources" / "zh" / f"{part['slug']}.zh.md"
        if not path.exists():
            continue
        blocks = parse_blocks(path)
        for block in blocks:
            kind = block["type"]
            if kind == "paragraph" and block["text"].startswith("|"):
                kind = "table-row"
            source[kind] += 1
    built: Counter[str] = Counter()
    with zipfile.ZipFile(epub) as archive:
        for name in archive.namelist():
            if not name.endswith(".xhtml") or name.endswith("title.xhtml") or name.endswith("nav.xhtml"):
                continue
            tree = ElementTree.fromstring(archive.read(name))
            for element in tree.iter():
                if element.tag == f"{XHTML}blockquote":
                    built["paragraph"] += 1
                elif element.tag == f"{XHTML}figure":
                    built["caption"] += 1
                elif element.tag == f"{XHTML}aside":
                    built["stat"] += 1
                elif element.tag in {f"{XHTML}h2", f"{XHTML}h3", f"{XHTML}h4"}:
                    built["heading"] += 1
                elif element.tag == f"{XHTML}ul":
                    built["list-group"] += 1
                elif element.tag == f"{XHTML}table":
                    built["table"] += 1
                elif element.tag == f"{XHTML}p" and "subhead" in (element.get("class") or ""):
                    built["subhead"] += 1
    print(f"{epub.name}")
    for kind in sorted(set(source) | set(built)):
        print(f"  {kind:12s} source={source.get(kind, 0):4d}  epub={built.get(kind, 0):4d}  {'ok' if source.get(kind, 0) == built.get(kind, 0) else 'DIFF'}")


if __name__ == "__main__":
    main()