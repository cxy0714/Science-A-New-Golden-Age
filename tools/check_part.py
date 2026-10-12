#!/usr/bin/env python3
"""Check one translated fragment of a chapter against the English line range it mirrors.

Used when a long chapter is translated in parallel chunks: each chunk covers an exact
line range of the English file, and this tool proves that the fragment contains the
same block sequence (count, kinds, and per-block endnote markers) as that range.

Usage:
  python tools/check_part.py chapter-02 1 34 sources/zh/_chapter-02.A.zh.md
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_bilingual import markers, parse_blocks  # noqa: E402


def main() -> None:
    if len(sys.argv) != 5:
        sys.exit(__doc__)
    slug, start, end, fragment = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), pathlib.Path(sys.argv[4])
    en = [b for b in parse_blocks(ROOT / "sources" / "en" / f"{slug}.en.md") if start <= b["line"] <= end]
    zh = parse_blocks(fragment if fragment.is_absolute() else ROOT / fragment)
    problems: list[str] = []
    if len(en) != len(zh):
        problems.append(f"block count differs: en lines {start}-{end} -> {len(en)} blocks, fragment -> {len(zh)}")
    for index, (a, b) in enumerate(zip(en, zh), start=1):
        label = f"block {index} (en line {a['line']})"
        if a["type"] != b["type"]:
            problems.append(f"{label}: kind differs ({a['type']} vs {b['type']})\n    en: {a['text'][:90]}\n    zh: {b['text'][:90]}")
        elif a["type"] == "heading" and a["level"] != b["level"]:
            problems.append(f"{label}: heading level differs ({a['level']} vs {b['level']})")
        elif markers(a["text"]) != markers(b["text"]):
            problems.append(f"{label}: markers differ (en={markers(a['text'])} zh={markers(b['text'])})")
    kinds = {}
    for block in en:
        kinds[block["type"]] = kinds.get(block["type"], 0) + 1
    print(f"en lines {start}-{end}: {len(en)} blocks {kinds}; fragment: {len(zh)} blocks")
    if problems:
        print("MISMATCH")
        for problem in problems:
            print("  -", problem)
        sys.exit(1)
    print("MATCH")


if __name__ == "__main__":
    main()