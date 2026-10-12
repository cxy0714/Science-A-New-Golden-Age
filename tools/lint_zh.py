#!/usr/bin/env python3
"""Lint the Chinese translation files with the checks that the old EPUB failed.

Catches exactly the defects that produced the "29 / 30 / 31" complaints:
  * page-number-like digits glued to sentence ends or standing alone on a line
  * half-width punctuation inside Chinese text
  * unbalanced 「」 quotes, odd numbers of markdown emphasis markers
  * table rows whose cell count no longer matches the English original
  * long stretches of Chinese without any punctuation (a paragraph fed whole to a
    machine translator typically shows up this way)
  * lines that are almost entirely ASCII letters and are not on the allow-list
    (footnote definitions, letterhead names, tables, the memo code line)

Usage: python tools/lint_zh.py [slug ...]
"""

from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_bilingual import parse_blocks  # noqa: E402

HAN_RANGE = "\u4e00-\u9fff"
HAN = re.compile(rf"[{HAN_RANGE}]")
HALF_PUNCT = re.compile(rf"(?:[{HAN_RANGE}])\s*([,;:!?])|([,;:!?])\s*(?:[{HAN_RANGE}])")
GLUED_DIGITS = re.compile(
    rf"[。！？；」】]\s*\d{{1,3}}\b(?!\s*(?:世纪|年代|年|月|日|亿|万|美元|财年|届|个|名|位|人|台|次|多))"
)
LONE_NUMBER = re.compile(r"^\d{1,3}\.?$")
ENGLISH_SENTENCE = re.compile(r"[A-Za-z]{3,}(?:\s+[A-Za-z]{2,}){5,}")
ALLOWED_ASCII = re.compile(
    r"^(\[\^\d+\]:|### Notes$|MICHAEL J\. KRATSIOS$|RUSSELL T\. VOUGHT$|NSTM-5 / M-26-16$|"
    r"FDA、NSF)",
)
URL = re.compile(r"https?://\S+|\]\([^)]*\)")


def ascii_ratio(text: str) -> float:
    letters = [c for c in text if not c.isspace()]
    if not letters:
        return 0.0
    return sum(1 for c in letters if ord(c) < 128) / len(letters)


def lint(slug: str) -> int:
    zh_path = ROOT / "sources" / "zh" / f"{slug}.zh.md"
    en_blocks = parse_blocks(ROOT / "sources" / "en" / f"{slug}.en.md")
    zh_blocks = parse_blocks(zh_path)
    issues: list[str] = []

    for index, block in enumerate(zh_blocks, start=1):
        text = block["text"]
        stripped = URL.sub("", text)
        label = f"{slug} block {index} (line {block['line']})"
        if HAN.search(stripped):
            half = HALF_PUNCT.search(stripped)
            if half:
                issues.append(
                    f"{label}: half-width {half.group(0).strip()!r} next to Chinese text: "
                    f"…{stripped[max(0, half.start() - 25):half.end() + 25]}…"
                )
            glued = GLUED_DIGITS.search(stripped)
            if glued:
                issues.append(
                    f"{label}: digit glued to sentence end: "
                    f"…{stripped[max(0, glued.start() - 30):glued.end() + 10]}…"
                )
            if stripped.count("「") != stripped.count("」"):
                issues.append(f"{label}: unbalanced 「」 ({stripped.count('「')} vs {stripped.count('」')})")
            for sentence in re.split(r"[。！？；]", stripped):
                if len(sentence) > 240:
                    issues.append(f"{label}: {len(sentence)} characters without punctuation: {sentence[:60]}…")
            if "  " in stripped:
                issues.append(f"{label}: double space")
        if LONE_NUMBER.match(text.strip()):
            issues.append(f"{label}: line is nothing but a number: {text.strip()!r} (page-number residue?)")
        if block["type"] != "heading" and stripped.count("*") % 2:
            issues.append(f"{label}: odd number of '*' (broken emphasis): {text[:60]}")
        if (
            block["type"] == "paragraph"
            and ascii_ratio(stripped) > 0.75
            and ENGLISH_SENTENCE.search(stripped)
            and not ALLOWED_ASCII.match(text.strip())
            and not re.match(r"^\|", stripped)
        ):
            issues.append(f"{label}: mostly untranslated ({ascii_ratio(stripped):.0%} ASCII): {text[:70]}")
        # Table rows must keep the English cell count.
        if text.strip().startswith("|") and index <= len(en_blocks):
            english = en_blocks[index - 1]["text"]
            if english.strip().startswith("|") and english.count("|") != text.count("|"):
                issues.append(f"{label}: table row has {text.count('|')} pipes, English has {english.count('|')}")
            elif english.strip().startswith("|") and not re.match(r"^[|\s:-]+$", text.strip()):
                en_cells = [c.strip() for c in english.strip("|").split("|")]
                zh_cells = [c.strip() for c in text.strip("|").split("|")]
                for position, (a, b) in enumerate(zip(en_cells, zh_cells), start=1):
                    if a in {"●", "○", "◐"} and b != a:
                        issues.append(f"{label}: cell {position} symbol changed: {a} -> {b}")

    print(f"\n=== {slug} ({len(zh_blocks)} blocks) ===")
    if issues:
        for issue in issues:
            print("  -", issue)
        print(f"  {len(issues)} issue(s)")
        return 1
    print("  clean")
    return 0


def main() -> None:
    slugs = sys.argv[1:] or [
        path.stem.replace(".zh", "")
        for path in sorted((ROOT / "sources" / "zh").glob("*.zh.md"))
        if not path.name.startswith("_")
    ]
    failures = sum(lint(slug) for slug in slugs)
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()