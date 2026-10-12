#!/usr/bin/env python3
"""Run the whole verification suite and print one pass/fail table.

Steps (each in its own process, output captured):
  1. verify_source.py <part>   — web edition vs official PDF, per part
  2. verify_markers.py <part>  — endnote numbers vs the printed PDF layer
  3. lint_zh.py                — page-number residue, punctuation, tables, untranslated lines
  4. build_bilingual.py        — block-for-block alignment of every part
  5. build_book_md.py          — combined book (fails if a part is unaligned)
  6. build_bilingual_epub.py   — both EPUBs (fails if a part is unaligned)
  7. check_epub.py             — XML, internal links, images, English/Chinese pairing

Usage: python tools/verify_all.py [--fast]     (--fast skips the PDF comparisons)
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

ROOT = pathlib.Path(__file__).resolve().parents[1]
PARTS = ["front", "chapter-01", "chapter-02", "chapter-03", "chapter-04", "chapter-05", "annex-fy2028"]
STEPS: list[tuple[str, list[str]]] = []


def run(label: str, arguments: list[str]) -> tuple[str, str, str]:
    result = subprocess.run(
        [sys.executable, *arguments],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    tail = [line for line in (result.stdout or "").splitlines() if line.strip()]
    summary = tail[-1].strip() if tail else ""
    if result.returncode != 0:
        errors = [line for line in (result.stderr or "").splitlines() if line.strip()]
        summary = (errors[-1].strip() if errors else summary) or "failed"
    return label, "PASS" if result.returncode == 0 else "FAIL", summary


def main() -> None:
    fast = "--fast" in sys.argv
    if not fast:
        for part in PARTS:
            STEPS.append((f"PDF↔web  {part}", ["tools/verify_source.py", part]))
            STEPS.append((f"markers  {part}", ["tools/verify_markers.py", part]))
    STEPS.extend(
        [
            ("zh lint", ["tools/lint_zh.py"]),
            ("alignment", ["tools/build_bilingual.py"]),
            ("combined markdown", ["tools/build_book_md.py"]),
            ("epub build", ["tools/build_bilingual_epub.py"]),
            ("epub check", ["tools/check_epub.py", "科学_一个新的黄金时代_中英对照.epub", "科学_一个新的黄金时代_中文.epub"]),
        ]
    )
    results = [run(label, arguments) for label, arguments in STEPS]
    width = max(len(label) for label, _, _ in results)
    print("\n=== verification summary ===")
    for label, status, summary in results:
        print(f"{label:<{width}}  {status}  {summary}")
    failures = [label for label, status, _ in results if status == "FAIL"]
    print(f"\n{len(results) - len(failures)}/{len(results)} passed")
    if failures:
        print("failed:", ", ".join(failures))
        sys.exit(1)


if __name__ == "__main__":
    main()