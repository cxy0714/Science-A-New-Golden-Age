#!/usr/bin/env python3
"""Align the printed PDF endnote list with the web endnote list by text similarity."""
from __future__ import annotations

import difflib
import json
import pathlib
import re

import fitz

ROOT = pathlib.Path(__file__).resolve().parents[1]
PDF = ROOT / "Science-A-New-Golden-Age.pdf"
OUT = ROOT / "tools" / "_note_list_alignment.txt"


def norm(text: str) -> str:
    text = text.replace("\u2019", "'")
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[^A-Za-z0-9 ]", " ", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def pdf_notes() -> list[tuple[int, str]]:
    doc = fitz.open(PDF)
    lines: list[str] = []
    for index in range(90, min(96, doc.page_count)):
        lines.extend(doc[index].get_text("text").splitlines())
    entries: list[tuple[int, str]] = []
    current_num = None
    buffer: list[str] = []
    for line in lines:
        stripped = line.strip()
        if re.fullmatch(r"\d{1,3}", stripped):
            if current_num is not None:
                entries.append((current_num, " ".join(buffer)))
            current_num = int(stripped)
            buffer = []
        elif current_num is not None and stripped and not re.match(r"^(Chapter|Annex|\d+$)", stripped):
            buffer.append(stripped)
    if current_num is not None:
        entries.append((current_num, " ".join(buffer)))
    return entries


def main() -> None:
    web = json.loads((ROOT / "sources" / "report.json").read_text(encoding="utf-8"))["footnotes"]
    pdf_entries = pdf_notes()
    lines = [f"pdf list entries: {len(pdf_entries)}  first={pdf_entries[0][0]} last={pdf_entries[-1][0]}"]
    web_keys = sorted(int(k) for k in web)
    lines.append(f"web list entries: {len(web_keys)} first={web_keys[0]} last={web_keys[-1]}")
    web_norm = {k: norm(web[str(k)]) for k in web_keys}
    mismatches = 0
    for offset in (0, -1, 1):
        ok = 0
        for num, text in pdf_entries:
            partner = web_norm.get(num + offset)
            if partner and difflib.SequenceMatcher(None, norm(text), partner).ratio() > 0.9:
                ok += 1
        lines.append(f"offset {offset:+d}: {ok}/{len(pdf_entries)} entries match")
    # Detailed comparison with the identity offset.
    for num, text in pdf_entries:
        partner = web_norm.get(num)
        ratio = difflib.SequenceMatcher(None, norm(text), partner).ratio() if partner else 0.0
        if ratio <= 0.9:
            mismatches += 1
            lines.append(f"\nMISMATCH pdf {num}: {text[:150]}")
            lines.append(f"         web {num}: {web.get(str(num), '<missing>')[:150]}")
            for probe in range(num - 3, num + 4):
                other = web_norm.get(probe)
                if other:
                    r2 = difflib.SequenceMatcher(None, norm(text), other).ratio()
                    if r2 > 0.85:
                        lines.append(f"         best web match: {probe} ({r2:.2f})")
    lines.append(f"\nidentity-offset mismatches: {mismatches}")
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()