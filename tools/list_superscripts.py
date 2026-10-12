#!/usr/bin/env python3
"""List superscript-sized digit spans per PDF page (to locate endnote markers)."""
from __future__ import annotations

import pathlib
import re
import sys
from collections import Counter

import fitz

ROOT = pathlib.Path(__file__).resolve().parents[1]
PDF = ROOT / "Science-A-New-Golden-Age.pdf"
OUT = ROOT / "tools" / "_front_markers.txt"


def main() -> None:
    first = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    last = int(sys.argv[2]) if len(sys.argv) > 2 else 19
    doc = fitz.open(PDF)
    lines: list[str] = []
    for index in range(first - 1, last):
        page = doc[index]
        data = page.get_text("dict")
        sizes = Counter()
        for block in data["blocks"]:
            for line in block.get("lines", []):
                for span in line["spans"]:
                    sizes[round(span["size"], 1)] += len(span["text"].strip())
        body = sizes.most_common(1)[0][0]
        found: list[tuple[str, str]] = []
        for block in data["blocks"]:
            for line in block.get("lines", []):
                text = "".join(span["text"] for span in line["spans"])
                for span in line["spans"]:
                    stripped = span["text"].strip()
                    if span["size"] < body - 0.8 and re.fullmatch(r"\d{1,3}\.?", stripped):
                        found.append((stripped, text.strip()[:90]))
        lines.append(f"--- page {index + 1} (body size {body}) ---")
        lines.append(f"  superscript digits: {[f[0] for f in found]}")
        for digit, context in found:
            lines.append(f"    {digit}: {context}")
    OUT.write_text("\n".join(line for line in lines if line is not None), encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()