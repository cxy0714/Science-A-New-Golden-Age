#!/usr/bin/env python3
"""Extract a clean, paragraph-accurate English text of the report from the official
web edition (sources/whitehouse-science.html).

Why the web edition: the PDF text layer wraps every visual line, splits words with
hyphens, injects page numbers and running headers into the body, and glues endnote
markers onto line ends. Translating from that layer produced mid-sentence breaks and
stray digits (e.g. "…，29 30 31…"). The web edition keeps real paragraphs.

Outputs
-------
sources/report.json          structured blocks (sections, paragraphs, lists, notes)
sources/en/<slug>.md         readable English text per part, for translation input
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag

ROOT = pathlib.Path(__file__).resolve().parents[1]
HTML = ROOT / "sources" / "whitehouse-science.html"
JSON_OUT = ROOT / "sources" / "report.json"
EN_DIR = ROOT / "sources" / "en"

PARTS = [
    ("front", "Front Matter: Letters and Summary", ("letter-of-transmittal", "presidents-letter", "summary")),
    ("chapter-01", "Chapter I: Introduction", ("chapter-1",)),
    ("chapter-02", "Chapter II: Revitalizing America's Science and Technology Enterprise", ("chapter-2",)),
    ("chapter-03", "Chapter III: Ensuring U.S. Dominance in Critical and Emerging Technologies", ("chapter-3",)),
    ("chapter-04", "Chapter IV: Ensuring That Science and Technology Better the Lives of All Americans", ("chapter-4",)),
    ("chapter-05", "Chapter V: A New Golden Age", ("chapter-5",)),
    ("annex-fy2028", "Annex: FY2028 R&D Priorities Memo", ("rdmemo",)),
    ("references", "References & Sources", ("index",)),
]

# Parts whose English text does not come from the web edition; this script must not
# overwrite their files (the FY2028 memo is extracted from its own PDF by
# tools/extract_annex.py, because the web edition only links to it).
EXTERNAL_SOURCES = {"annex-fy2028": "tools/extract_annex.py"}


def note_number(anchor: Tag) -> str | None:
    """Printed-report endnote number for a footnote link or note item.

    The web edition's visible marker numbering drifted: each marker carries the
    id of its list item (`#fn-N`) rather than the number printed in the report,
    and the list skips a number. The printed PDF numbers the notes 1..185, and
    anchor id N corresponds to printed note N-1. Aligning on `id - 1` reproduces
    the printed numbering exactly (cross-checked with tools/align_note_lists.py).
    """
    href = anchor.get("href") or anchor.get("id") or ""
    match = re.search(r"fn-?(\d+)", href)
    if not match:
        return None
    return str(int(match.group(1)) - 1)


def inline(node: Tag) -> str:
    """Render inline markup as light markdown; footnote refs become [^n]."""
    out: list[str] = []
    for child in node.children:
        if isinstance(child, NavigableString):
            out.append(str(child))
            continue
        if not isinstance(child, Tag):
            continue
        classes = child.get("class", [])
        if child.name == "sup" and "footnote-ref" in classes:
            link = child.find("a")
            number = note_number(link) if link is not None else None
            number = number or child.get_text(strip=True)
            out.append(f"[^{number}]")
        elif child.name == "sup":
            out.append(f"[^{child.get_text(strip=True)}]")
        elif child.name == "em":
            out.append(f"*{inline(child).strip()}*")
        elif child.name == "strong":
            out.append(f"**{inline(child).strip()}**")
        elif child.name == "a":
            text = inline(child).strip()
            href = child.get("href", "")
            if not href or href.startswith("#"):
                out.append(text)
            else:
                out.append(f"[{text}]({href})")
        elif child.name == "br":
            out.append(" ")
        else:
            out.append(inline(child))
    return "".join(out)


def clean(text: str) -> str:
    text = text.replace("\u00a0", " ").replace("\u2009", " ").replace("\u202f", " ")
    text = text.replace("**&**", "&")  # the source bolds the ampersand in "R&D"
    text = re.sub(r"\*{4,}", "**", text)  # nested <strong><strong> headings
    # The source occasionally closes a bold lead-in right against the next word.
    text = re.sub(r"(\*\*[^*]+\*\*)(?=[A-Za-z0-9])", r"\1 ", text)
    text = re.sub(r"([A-Za-z0-9])(\*\*[A-Z])", r"\1 \2", text)
    text = re.sub(r"[ \t\r\n]+", " ", text)
    text = re.sub(r"\s+([,.;:!?%)\]\u2019\u201d])", r"\1", text)
    text = re.sub(r"([(\[\u201c])\s+", r"\1", text)
    text = re.sub(r"\s+(\[\^\d+\])", r"\1", text)
    text = re.sub(r"\[\^(\d+)\]\s+", r"[^\1] ", text)
    return text.strip()


def render_blocks(container: Tag) -> list[dict]:
    blocks: list[dict] = []
    for child in container.find_all(recursive=False):
        classes = child.get("class", [])
        if child.name == "p":
            text = clean(inline(child))
            if not text:
                continue
            kind = "caption" if "figure-caption" in classes else "paragraph"
            if "section-subhead" in classes:
                kind = "subhead"
            if "refs-intro" in classes:
                kind = "note"
            blocks.append({"type": kind, "text": text})
        elif child.name in {"ul", "ol"}:
            items = [clean(inline(li)) for li in child.find_all("li", recursive=False)]
            if items:
                blocks.append({"type": "list", "ordered": child.name == "ol", "items": items})
        elif child.name == "blockquote":
            # Decorative pull quotes repeat body sentences; keep out of the translation.
            blocks.append({"type": "pullquote", "text": clean(inline(child))})
        elif child.name == "div" and "stat-callout" in classes:
            blocks.append({"type": "stat", "text": clean(child.get_text(" ", strip=True))})
        elif child.name == "div" and "table-wrap" in classes:
            rows = []
            for tr in child.find_all("tr"):
                cells = [clean(inline(c)) for c in tr.find_all(["th", "td"])]
                rows.append(cells)
            blocks.append({"type": "table", "rows": rows})
        elif child.name == "div" and "chapter-divider" in classes:
            continue
        elif child.name == "div":
            blocks.extend(render_blocks(child))
    return blocks


def section_record(sec: Tag) -> dict | None:
    classes = sec.get("class", [])
    if "hero" in classes:
        return None
    eyebrow = sec.find("div", class_="section-eyebrow") or sec.find("div", class_="chapter-eyebrow")
    eyebrow_parts: list[str] = []
    if eyebrow is not None:
        eyebrow_parts = [clean(eyebrow.get_text(" ", strip=True))]
    head = sec.find(["h1", "h2", "h3"])
    title = clean(head.get_text(" ", strip=True)) if head else ""
    if "chapter-cover" in classes:
        num = sec.find("div", class_="chapter-num-display")
        blocks = render_blocks(sec.find("div", class_="chapter-cover-inner") or sec)
        return {
            "id": sec.get("id", ""),
            "kind": "chapter-cover",
            "number": clean(num.get_text(" ", strip=True)) if num else "",
            "title": title,
            "eyebrow": eyebrow_parts,
            "blocks": [b for b in blocks if b["type"] != "heading"],
        }
    column = sec.find("div", class_="reading-column")
    blocks = render_blocks(column) if column is not None else []
    # Only the "References & Sources" section is the endnote list. The FY2028 memo
    # section shares the `reading--refs` class but carries the memo's own content.
    if sec.get("id") == "index":
        kind = "references"
    elif "reading" in classes:
        kind = "section"
    else:
        kind = "other"
    return {
        "id": sec.get("id", ""),
        "kind": kind,
        "number": re.sub(r"^(\S+).*$", r"\1", eyebrow_parts[0]) if eyebrow_parts and re.match(r"^[IVX]+\.\d+", eyebrow_parts[0]) else "",
        "part_label": eyebrow_parts[0] if eyebrow_parts else "",
        "title": title,
        "blocks": blocks,
    }


def footnotes(soup: BeautifulSoup) -> dict[str, str]:
    notes: dict[str, str] = {}
    for li in soup.find_all("li", class_="footnote-item"):
        text_el = li.find("span", class_="footnote-text")
        if text_el is None:
            continue
        number = note_number(li) or re.sub(r"\D", "", li.get("id", ""))
        notes[number] = clean(inline(text_el))
    return notes


def markdown(part_title: str, sections: list[dict], notes: dict[str, str]) -> str:
    lines = [f"# {part_title}", ""]
    for sec in sections:
        if sec["kind"] == "chapter-cover":
            # The chapter cover only repeats the part title; keep any extra blocks
            # (e.g. the closing chapter's statement) but not a duplicate heading.
            for block in sec["blocks"]:
                if block["type"] == "paragraph":
                    lines += [block["text"], ""]
            continue
        if sec["kind"] == "references":
            lines += [f"## {sec['title']}", ""]
            for num in sorted(notes, key=lambda n: int(n)):
                lines += [f"[^{num}]: {notes[num]}", ""]
            continue
        if sec["title"]:
            label = f"{sec['number']} " if sec["number"] else ""
            lines += [f"### {label}{sec['title']}", ""]
        for block in sec["blocks"]:
            if block["type"] == "paragraph":
                lines += [block["text"], ""]
            elif block["type"] == "subhead":
                text = block["text"]
                lines += [text if text.startswith("**") else f"**{text}**", ""]
            elif block["type"] == "caption":
                lines += [f"*{block['text']}*", ""]
            elif block["type"] == "stat":
                lines += [f"> {block['text']}", ""]
            elif block["type"] == "list":
                for item in block["items"]:
                    lines.append(f"- {item}")
                lines.append("")
            elif block["type"] == "table":
                for index, row in enumerate(block["rows"]):
                    lines.append("| " + " | ".join(row) + " |")
                    if index == 0:  # markdown needs a delimiter row under the header
                        lines.append("|" + " --- |" * len(row))
                lines.append("")
            elif block["type"] == "pullquote":
                lines += [f"<!-- pullquote: {block['text']} -->", ""]
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    soup = BeautifulSoup(HTML.read_text(encoding="utf-8"), "html.parser")
    report = soup.find("main", class_="report")
    if report is None:
        sys.exit("report container not found")
    all_sections = [section_record(sec) for sec in report.find_all("section", recursive=False)]
    all_sections = [s for s in all_sections if s]
    notes = footnotes(soup)

    parts = []
    for slug, title, prefixes in PARTS:
        sections = [s for s in all_sections if any(s["id"] == p or s["id"].startswith(p + "-") for p in prefixes)]
        parts.append({"slug": slug, "title": title, "sections": sections})

    JSON_OUT.write_text(
        json.dumps({"footnotes": notes, "parts": parts}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    EN_DIR.mkdir(parents=True, exist_ok=True)
    for part in parts:
        if part["slug"] in EXTERNAL_SOURCES:
            # The memo text lives in its own PDF; tools/extract_annex.py owns this file.
            print(f"  (keeping {part['slug']}.en.md: produced by {EXTERNAL_SOURCES[part['slug']]})")
            continue
        (EN_DIR / f"{part['slug']}.en.md").write_text(
            markdown(part["title"], part["sections"], notes), encoding="utf-8"
        )

    print(f"sections: {len(all_sections)}  footnotes: {len(notes)}")
    for part in parts:
        words = sum(
            len(b.get("text", "").split()) + sum(len(i.split()) for i in b.get("items", []))
            for s in part["sections"]
            for b in s["blocks"]
        )
        print(f"  {part['slug']:14s} sections={len(part['sections']):3d} words≈{words}")


if __name__ == "__main__":
    main()