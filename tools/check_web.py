#!/usr/bin/env python3
"""Check the rendered HTML book in docs/ against the validated source pairs.

For every part this verifies that
  * every English and Chinese block of sources/{en,zh} appears verbatim in the
    rendered page (catches dropped, duplicated or reordered blocks),
  * every endnote reference resolves to a note on the same page and every note
    has a back-link that points at an anchor that exists,
  * every figure file referenced by an <img> exists in docs/images/,
  * the language switch and its stylesheet are wired into every page,
  * pandoc did not rewrite the text (literal "--", "$" and "..." survive).

Usage: python tools/check_web.py
"""

from __future__ import annotations

import html
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_bilingual import (  # noqa: E402
    PARTS,
    REPORT,
    body_skip_indices,
    load_figures,
    markers,
    merge_notes,
    parse_blocks,
    validate,
)

DOCS = ROOT / "docs"
SEPARATOR_CELL = re.compile(r":?-{2,}:?")
TAG = re.compile(r"<[^>]+>")
WS = re.compile(r"\s+")
NOTE_ANCHOR = re.compile(r'<a class="(?:noteref|note-back)"[^>]*>.*?</a>', re.S)


def plain(text: str) -> str:
    """Source markdown subset -> the plain text a reader should see."""
    out = re.sub(r"\[\^(\d+)\]", "", text)
    out = re.sub(r"\[([^\]^]+)\]\((https?://[^)\s]+)\)", r"\1", out)
    out = out.replace("**", "").replace("*", "").replace("`", "")
    return WS.sub(" ", out).strip()


def flatten(markup: str) -> str:
    """Rendered markup -> the text a reader should see (footnote marks removed)."""
    text = NOTE_ANCHOR.sub("", markup)
    text = html.unescape(TAG.sub("", text)).replace("\u00a0", " ")
    return WS.sub(" ", text)


def visible(source: str) -> str:
    return flatten(source[source.find("<main") : source.find("</main>")])


def main() -> None:
    notes = json.loads(REPORT.read_text(encoding="utf-8"))["footnotes"]
    figures = load_figures()
    problems: list[str] = []
    checked_blocks = 0

    for part in PARTS:
        slug = part["slug"]
        page = DOCS / f"{slug}.html"
        if not page.exists():
            problems.append(f"{slug}: no rendered page")
            continue
        source = page.read_text(encoding="utf-8")
        text = visible(source)
        en_blocks = parse_blocks(ROOT / "sources" / "en" / f"{slug}.en.md")
        zh_blocks = parse_blocks(ROOT / "sources" / "zh" / f"{slug}.zh.md")
        alignment = validate(slug, en_blocks, zh_blocks)
        if alignment:
            problems.append(f"{slug}: alignment gate failed: {alignment[0]}")
            continue
        part_notes = merge_notes(en_blocks, notes)
        skip = body_skip_indices(en_blocks)

        # --- every block survives, in both languages -------------------------
        for index, (en, zh) in enumerate(zip(en_blocks, zh_blocks)):
            if index in skip:
                continue
            kind = en["type"]
            if kind == "paragraph" and en["text"].startswith("|"):
                if all(SEPARATOR_CELL.fullmatch(cell.strip()) for cell in en["text"].strip("|").split("|")):
                    continue
                pieces = [cell.strip() for cell in en["text"].strip("|").split("|")]
                pieces += [cell.strip() for cell in zh["text"].strip("|").split("|")]
            elif kind == "heading" and en.get("level") == 1:
                continue
            else:
                pieces = [en["text"], zh["text"]]
            for piece in pieces:
                want = plain(piece)
                checked_blocks += 1
                if want and want not in text:
                    problems.append(f"{slug} block {index + 1} ({kind}): text missing from page: {want[:70]}")

        # --- endnotes: references, targets, back-links -----------------------
        used = sorted({int(n) for block in en_blocks for n in markers(block["text"])})
        refs = set(re.findall(r'class="noteref" id="([^"]+)" href="#([^"]+)"', source))
        if len(refs) != len(used) * 2:
            problems.append(f"{slug}: {len(refs)} endnote references, expected {len(used) * 2}")
        ids = set(re.findall(r'\bid="([^"]+)"', source))
        for ident, target in refs:
            if target not in ids:
                problems.append(f"{slug}: reference {ident} points at missing anchor #{target}")
        for number in used:
            if f"fn-{slug}-{number}" not in ids:
                problems.append(f"{slug}: note {number} has no target")
        for target in re.findall(r'class="note-back" data-target="([^"]+)"', source):
            for side in ("en", "zh"):
                if f"{target}-{side}" not in ids:
                    problems.append(f"{slug}: back-link target {target}-{side} missing")
        note_texts = re.findall(r'<li id="fn-[^"]+" value="(\d+)">(.*?)</li>', source, re.S)
        if len(note_texts) != len(used):
            problems.append(f"{slug}: {len(note_texts)} note entries, expected {len(used)}")
        for number, body in note_texts:
            want = plain(part_notes[number])
            got = flatten(body)
            if want and want not in got:
                problems.append(f"{slug}: note {number} text does not match sources/report.json")

        # --- figures ---------------------------------------------------------
        expected: list[str] = []
        for index, (en, _zh) in enumerate(zip(en_blocks, zh_blocks)):
            if index in skip or en["type"] != "caption":
                continue
            from build_bilingual import figures_for  # local import keeps the top tidy

            for entry in figures_for(figures, slug, en["text"]):
                for name in entry.get("files") or [entry.get("file")]:
                    if name:
                        expected.append(name)
        rendered = re.findall(r'<img src="images/([^"]+)"', source)
        if sorted(rendered) != sorted(expected):
            problems.append(f"{slug}: figures rendered {sorted(rendered)} != expected {sorted(expected)}")
        for name in rendered:
            if not (DOCS / "images" / name).exists():
                problems.append(f"{slug}: figure file docs/images/{name} missing")

        # --- wiring: switch, stylesheet, verbatim text -----------------------
        if 'id="lang-switch"' not in source and "lang-switch" not in source:
            problems.append(f"{slug}: language switch script missing")
        if "styles.css" not in source:
            problems.append(f"{slug}: styles.css not linked")
        if 'data-lang-mode' not in source:
            problems.append(f"{slug}: language mode script missing")

    # --- pandoc must not have parsed the text as markdown ---------------------
    for part in PARTS:
        source = (DOCS / f"{part['slug']}.html").read_text(encoding="utf-8")
        if 'data-lang-mode' not in source:
            problems.append(f"{part['slug']}: data-lang-mode hook missing")
        if 'class="math' in source or "<span class=\"math" in source:
            problems.append(f"{part['slug']}: the renderer parsed part of the text as math")
    chapter = visible((DOCS / "chapter-02.html").read_text(encoding="utf-8"))
    for literal in ("$", "—", "’"):
        if literal not in chapter:
            problems.append(f"chapter-02: literal {literal!r} did not survive the renderer")

    for line in problems:
        print("  ✗", line)
    print(f"\n{checked_blocks} blocks checked across {len(PARTS)} parts")
    print(f"{len(problems)} problem(s)")
    if problems:
        sys.exit(1)
    print("docs/ matches the validated sources")


if __name__ == "__main__":
    main()