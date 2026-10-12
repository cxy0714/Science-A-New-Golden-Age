#!/usr/bin/env python3
"""Cross-check the web edition against the official PDF text layer.

Confirms that the clean HTML source contains the whole body text of a part
(and reveals anything only present in the PDF). Reports word-level differences
so gaps cannot slip into the translation.

Usage: python tools/verify_source.py [slug]      (default: chapter-01)
"""

from __future__ import annotations

import difflib
import pathlib
import re
import sys

import fitz

ROOT = pathlib.Path(__file__).resolve().parents[1]
PDF = ROOT / "Science-A-New-Golden-Age.pdf"

# Physical PDF page ranges (1-based, inclusive) of each part's body text, located by
# tools/find_pages.py using body-specific sentences.
PAGE_RANGES = {
    # Front matter: letter of transmittal (v–vii), President's letter (viii–ix),
    # report summary (x–xvii). The printed table of contents (physical pages 3–4)
    # is deliberately outside the range: it is navigation, not report text.
    "front": (5, 18),
    "chapter-01": (19, 30),
    "chapter-02": (31, 50),
    "chapter-03": (51, 64),
    "chapter-04": (65, 74),
    "chapter-05": (75, 95),
    # The FY2028 memorandum is published as its own PDF; its 14 pages are the source
    # of the annex part (PDF_OVERRIDES below).
    "annex-fy2028": (1, 14),
}

# Parts whose text lives in a different PDF.
PDF_OVERRIDES = {
    "annex-fy2028": ROOT / "sources" / "White-House-Fiscal-Year-2028-RD-Priorities-Memorandum.pdf",
}

NOISE_LOWER = re.compile(
    r"^(?:\d{1,3}|[ivxlcdm]{1,7}|chapter [ivx]+(?:\s*[-–—]\s*.*)?|summary of the report)$",
    re.I,
)
NOISE_CAPS = re.compile(r"^[A-Z][A-Z0-9 ,&.'’\-–—()/]{6,}$")


def is_noise(line: str) -> bool:
    return bool(NOISE_LOWER.match(line) or NOISE_CAPS.match(line))


def normalise(text: str) -> str:
    text = text.replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u2014", "-").replace("\u2013", "-").replace("\u2010", "-")
    text = re.sub(r"\[\^\d+\]", " ", text)
    text = re.sub(r"[^A-Za-z0-9$%'.,;:()\-/\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def pdf_part_text(slug: str) -> str:
    first, last = PAGE_RANGES[slug]
    doc = fitz.open(PDF_OVERRIDES.get(slug, PDF))
    chunks: list[str] = []
    for page_index in range(first - 1, last):
        page = doc[page_index].get_text("text")
        lines = []
        for line in page.splitlines():
            stripped = line.strip()
            if not stripped or is_noise(stripped):
                continue
            lines.append(stripped)
        joined = "\n".join(lines)
        joined = re.sub(r"(?<=[A-Za-z])-\n(?=[a-z])", "", joined)
        chunks.append(joined.replace("\n", " "))
    return normalise(" ".join(chunks))


def web_part_text(slug: str) -> str:
    path = ROOT / "sources" / "en" / f"{slug}.en.md"
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"^#{1,6}.*$", " ", text, flags=re.M)
    text = re.sub(r"^<!--.*?-->$", " ", text, flags=re.M)
    return normalise(text)


def main() -> None:
    slug = sys.argv[1] if len(sys.argv) > 1 else "chapter-01"
    pdf_words = pdf_part_text(slug).split()
    web_words = web_part_text(slug).split()
    print(f"{slug}: PDF words={len(pdf_words)}  web words={len(web_words)}")
    matcher = difflib.SequenceMatcher(None, pdf_words, web_words, autojunk=False)
    print(f"similarity: {matcher.ratio():.4f}")
    problems = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        left = " ".join(pdf_words[i1:i2])
        right = " ".join(web_words[j1:j2])
        if tag == "replace" and abs((i2 - i1) - (j2 - j1)) <= 3 and min(i2 - i1, j2 - j1) > 0:
            # Tolerate small wording/typographic differences.
            if len(left) < 60 and len(right) < 60:
                continue
        problems += 1
        print(f"\n[{tag}] PDF({i2 - i1}w): {left[:400]}")
        print(f"      WEB({j2 - j1}w): {right[:400]}")
    print(f"\ndifference clusters: {problems}")


if __name__ == "__main__":
    main()