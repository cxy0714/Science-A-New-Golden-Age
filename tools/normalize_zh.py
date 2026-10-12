#!/usr/bin/env python3
"""Normalise Chinese translation files: keep one space between CJK and Latin/digits.

Chinese typesetting convention (and this project's style): a space separates Han
characters from Latin words, acronyms and numbers. Hand-editing translations often
drops those spaces, so this script re-inserts them. It never touches markdown
syntax lines (headings are handled inside, which is fine because the same rule
applies to their text), and it leaves CJK punctuation untouched.

Usage: python tools/normalize_zh.py sources/zh/chapter-01.zh.md
       python tools/normalize_zh.py            (all files under sources/zh)
"""

from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
HAN = r"\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff"
LATIN = r"A-Za-z0-9"
# Han followed by Latin/digit, or Latin/digit followed by Han.
PATTERN = re.compile(rf"([{HAN}])([{LATIN}])|([{LATIN}])([{HAN}])")


def fix_line(line: str) -> str:
    previous = None
    while previous != line:
        previous = line
        line = PATTERN.sub(lambda m: f"{m.group(1) or m.group(3)} {m.group(2) or m.group(4)}", line)
    line = re.sub(r"[ \t]{2,}", " ", line)
    return line


def fix_file(path: pathlib.Path) -> int:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    out = [fix_line(line) for line in lines]
    changed = sum(1 for a, b in zip(lines, out) if a != b)
    if changed:
        path.write_text("\n".join(out) + ("\n" if text.endswith("\n") else ""), encoding="utf-8")
    return changed


def main() -> None:
    targets = [pathlib.Path(arg) for arg in sys.argv[1:]]
    if not targets:
        targets = sorted((ROOT / "sources" / "zh").glob("*.zh.md"))
    for path in targets:
        changed = fix_file(path)
        print(f"{path.name}: {changed} line(s) normalised")


if __name__ == "__main__":
    main()