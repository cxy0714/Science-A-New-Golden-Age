#!/usr/bin/env python3
"""Verify every endnote marker number in the extracted text against the printed PDF.

Matches each marker by its preceding words in the PDF text layer (where the marker
digit is glued to the last word) and reports any number that disagrees.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys

import fitz

ROOT = pathlib.Path(__file__).resolve().parents[1]
PDF = ROOT / "Science-A-New-Golden-Age.pdf"
OUT = ROOT / "tools" / "_marker_check.txt"
PAGE_RANGE = {"chapter-01": (19, 30), "chapter-02": (31, 50), "chapter-03": (51, 64),
              "chapter-04": (65, 74), "chapter-05": (75, 90),
              "annex-fy2028": (1, 14)}
# Parts that carry no numbered endnotes at all: the printed front matter has none
# (checked with tools/list_superscripts.py), so there is nothing to verify.
NO_MARKERS = {"front"}
PDF_OVERRIDES = {
    "annex-fy2028": ROOT / "sources" / "White-House-Fiscal-Year-2028-RD-Priorities-Memorandum.pdf",
}


def pdf_words(slug: str) -> list[str]:
    first, last = PAGE_RANGE[slug]
    doc = fitz.open(PDF_OVERRIDES.get(slug, PDF))
    text = "\n".join(doc[i].get_text("text") for i in range(first - 1, last))
    text = re.sub(r"(?<=[A-Za-z])-\n(?=[a-z])", "", text)
    return re.sub(r"\s+", " ", text).split()


def main() -> None:
    slug = sys.argv[1] if len(sys.argv) > 1 else "chapter-01"
    md = (ROOT / "sources" / "en" / f"{slug}.en.md").read_text(encoding="utf-8")
    md = re.sub(r"^#{1,6}.*$", " ", md, flags=re.M)
    md = re.sub(r"^<!--.*?-->$", " ", md, flags=re.M)
    words = re.sub(r"\s+", " ", md).split()
    if slug in NO_MARKERS:
        count = sum(1 for token in words if re.search(r"\[\^\d+\]", token))
        print(f"{slug}: no numbered endnotes expected; markers in the text: {count}")
        return
    pdf = pdf_words(slug)
    pdf_joined = " ".join(pdf)
    lines = [f"{slug}: markers in web text vs printed PDF"]
    checked = agreed = 0
    for index, token in enumerate(words):
        match = re.search(r"\[\^(\d+)\]([*_]*)$", token)
        if not match:
            continue
        web_number = match.group(1)
        head = token[:match.start()]
        probe_words = words[max(0, index - 4):index] + ([head] if head else [])
        probe = re.sub(r"\[\^\d+\]", "", " ".join(probe_words)).strip()
        position = pdf_joined.find(probe) if probe else -1
        checked += 1
        if position < 0:
            lines.append(f"  [^{web_number}] context not found: …{probe[-60:]!r}")
            continue
        after = pdf_joined[position + len(probe):position + len(probe) + 24]
        pdf_marker = re.match(r"\s*(\d{1,3})", after)
        if pdf_marker and pdf_marker.group(1) == web_number:
            agreed += 1
        else:
            lines.append(f"  [^{web_number}] PDF shows "
                         f"{pdf_marker.group(1) if pdf_marker else '?'} …{probe[-60:]!r}{after[:20]!r}")
    lines.append(f"\nmarkers checked: {checked}  agreed with printed PDF: {agreed}")
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"checked {checked}, agreed {agreed}")


if __name__ == "__main__":
    main()