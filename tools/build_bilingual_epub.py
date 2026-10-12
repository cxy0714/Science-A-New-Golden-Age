#!/usr/bin/env python3
"""Build the bilingual (English/Chinese) EPUB from the validated part sources.

The generator is a pure function of:
  sources/en/<slug>.en.md   (English, extracted from the official web edition and
                             word-compared against the printed PDF)
  sources/zh/<slug>.zh.md   (Chinese translation, block-for-block mirror)
  sources/report.json       (endnote texts, printed-edition numbering)
  对照稿/images/manifest.json (figures)

It refuses to emit a book unless every part passes the same alignment gate as
tools/build_bilingual.py. Footnotes are real hyperlinks (epub:type noteref/footnote),
figures carry their captions, and there is no PDF page furniture anywhere.

Usage:
  python tools/build_bilingual_epub.py            # bilingual + Chinese-only editions
  python tools/build_bilingual_epub.py --bilingual-only
"""

from __future__ import annotations

import html
import json
import pathlib
import re
import shutil
import sys
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_bilingual import (  # noqa: E402
    PARTS,
    REPORT,
    figures_for,
    load_figures,
    markers,
    parse_blocks,
    validate,
)

OUT_BI = ROOT / "科学_一个新的黄金时代_中英对照.epub"
OUT_ZH = ROOT / "科学_一个新的黄金时代_中文.epub"
BOOK_ID = "urn:uuid:science-a-new-golden-age-bilingual-2026"
DATE = "2026-08-15"

NOTE_REF = re.compile(r"\[\^(\d+)\]")
MD_LINK = re.compile(r"\[([^\]^]+)\]\((https?://[^)\s]+)\)")
BOLD = re.compile(r"\*\*([^*]+)\*\*")
ITALIC = re.compile(r"\*([^*]+)\*")
TITLE_ZH = "科学：一个新的黄金时代"
TITLE_EN = "Science: A New Golden Age"

STYLE = """@charset "utf-8";
body { font-family: serif; line-height: 1.7; margin: 6%; color: #191919; }
h1 { font-size: 1.6em; line-height: 1.3; margin: 0 0 .2em; }
h1 .en, h2 .en { display: block; font-size: .62em; font-weight: normal; font-style: italic; color: #666; margin-top: .25em; }
h2 { font-size: 1.25em; margin: 1.6em 0 .4em; }
h3 { font-size: 1.1em; margin: 1.3em 0 .3em; }
h4 { font-size: 1em; margin: 1.1em 0 .3em; }
p { margin: 0 0 .85em; text-align: justify; }
blockquote.en { margin: 0 0 .45em; padding: 0 0 0 .8em; border-left: 2px solid #d8d8d8; color: #5a5a5a; font-size: .88em; }
p.zh { margin: 0 0 1.35em; }
p.subhead { font-weight: bold; margin: 1.4em 0 .1em; }
p.subhead-en { font-style: italic; color: #666; margin: 0 0 1em; font-size: .9em; }
aside.stat { margin: 1.2em 0; padding: .6em .9em; border: 1px solid #ddd; border-left: 4px solid #254f75; background: #f7f9fb; }
aside.stat .num { display: block; font-size: .85em; color: #555; font-style: italic; }
aside.stat strong { font-size: 1.05em; }
figure { margin: 1.4em 0; text-align: center; }
figure img { max-width: 100%; height: auto; }
figcaption { font-size: .85em; color: #555; margin-top: .5em; text-align: left; }
figcaption .en { display: block; font-style: italic; color: #777; }
table.data { border-collapse: collapse; width: 100%; font-size: .85em; margin: 1em 0; }
table.data th, table.data td { border: 1px solid #ccc; padding: .35em .5em; text-align: left; }
section.notes { margin-top: 2.5em; border-top: 1px solid #ddd; padding-top: 1em; }
section.notes ol { padding-left: 1.4em; }
section.notes li { font-size: .82em; color: #444; margin-bottom: .5em; }
a { color: #254f75; text-decoration: none; }
a.noteref { vertical-align: super; font-size: .7em; }
p.source, p.notice, p.kicker, p.subtitle { text-align: center; color: #555; }
body.title-page { text-align: center; padding-top: 14%; }
body.title-page h1 { font-size: 2.05em; }
body.title-page .subtitle { font-size: 1.15em; margin-top: .2em; }
p.kicker { letter-spacing: .12em; font-size: .8em; text-transform: uppercase; }
hr { border: 0; border-top: 1px solid #ddd; margin: 2em 0; }
ul { padding-left: 1.3em; } li { margin-bottom: .7em; }
"""


def inline(text: str, slug: str) -> str:
    """Markdown subset -> XHTML (bold, italics, links, endnote references)."""
    out = html.escape(text, quote=False)

    def note_ref(match: re.Match[str]) -> str:
        number = match.group(1)
        return (
            f'<a class="noteref" id="fnref-{slug}-{number}" href="#fn-{number}" '
            f'epub:type="noteref"><sup>{number}</sup></a>'
        )

    out = NOTE_REF.sub(note_ref, out)
    out = MD_LINK.sub(lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>', out)
    out = BOLD.sub(lambda m: f"<strong>{m.group(1)}</strong>", out)
    out = ITALIC.sub(lambda m: f"<em>{m.group(1)}</em>", out)
    return out


def notes_section(slug: str, numbers: list[int], notes: dict[str, str]) -> str:
    if not numbers:
        return ""
    items = []
    for number in numbers:
        body = inline(notes[str(number)], slug)
        items.append(
            f'<li id="fn-{number}" epub:type="footnote">{body} '
            f'<a href="#fnref-{slug}-{number}" class="back">↩</a></li>'
        )
    return (
        '<section class="notes" epub:type="endnotes"><h2>脚注 · Notes</h2><ol>'
        + "".join(items)
        + "</ol></section>"
    )


def table_xhtml(rows: list[list[str]], slug: str) -> str:
    if not rows:
        return ""
    head, *body = rows
    head_html = "".join(f"<th>{inline(cell, slug)}</th>" for cell in head)
    body_html = "".join(
        "<tr>" + "".join(f"<td>{inline(cell, slug)}</td>" for cell in row) + "</tr>" for row in body
    )
    return f'<table class="data"><thead><tr>{head_html}</tr></thead><tbody>{body_html}</tbody></table>'


def blocks_to_xhtml(blocks: list[dict], figures: list[dict], slug: str, bilingual: bool) -> str:
    chunks: list[str] = []
    index = 0
    while index < len(blocks):
        block = blocks[index]
        kind = block["type"]
        if kind == "list" or (kind == "paragraph" and block["text"].startswith("|")):
            # Group consecutive list items, and consecutive table rows, into one element.
            if kind == "list":
                items = []
                while index < len(blocks) and blocks[index]["type"] == "list":
                    items.append(inline(blocks[index]["text"], slug))
                    index += 1
                chunks.append("<ul>" + "".join(f"<li>{item}</li>" for item in items) + "</ul>")
            else:
                rows = []
                while index < len(blocks) and blocks[index]["text"].startswith("|"):
                    cells = [cell.strip() for cell in blocks[index]["text"].strip("|").split("|")]
                    if not all(set(cell) <= {"-", " ", ":"} and cell for cell in cells):
                        rows.append(cells)
                    index += 1
                chunks.append(table_xhtml(rows, slug))
            continue
        index += 1
        if kind == "heading":
            if block.get("level") == 1:
                continue
            level = min(4, max(2, block["level"]))
            chunks.append(
                f'<h{level} id="{slug}-s{index}">{inline(block["text"], slug)}</h{level}>'
            )
        elif kind == "subhead":
            chunks.append(f'<p class="subhead">{inline(block["text"], slug)}</p>')
        elif kind == "stat":
            chunks.append(f'<aside class="stat">{inline(block["text"], slug)}</aside>')
        elif kind == "caption":
            entries = figures_for(figures, slug, block["text"])
            alternative = re.sub(r"\[\^\d+\]|[*`]", "", block["text"]).strip()
            images = "".join(
                f'<img src="images/{name}" alt="{html.escape(alternative, quote=True)}"/>'
                for entry in entries
                for name in (entry.get("files") or [entry.get("file")])
                if name
            )
            caption = f"<figcaption>{inline(block['text'], slug)}"
            if bilingual and "en" in block:
                caption += f'<span class="en">{inline(block["en"], slug)}</span>'
            caption += "</figcaption>"
            chunks.append(f"<figure>{images}{caption}</figure>" if images else f"<figure>{caption}</figure>")
        else:
            text = block["text"]
            if bilingual and "en" in block:
                chunks.append(f'<blockquote class="en">{inline(block["en"], slug)}</blockquote>')
            chunks.append(f'<p class="zh">{inline(text, slug)}</p>')
    return "\n".join(chunks)


def part_document(part: dict, en_blocks: list[dict], zh_blocks: list[dict], figures: list[dict], notes: dict[str, str], bilingual: bool) -> str:
    # Pair English and Chinese per block for the bilingual edition.
    merged: list[dict] = []
    for en, zh in zip(en_blocks, zh_blocks):
        block = dict(zh)
        if en["type"] != "heading" or en.get("level") != 1:
            block["en"] = en["text"]
        merged.append(block)
    numbers = sorted({int(n) for block in en_blocks for n in markers(block["text"])})
    body = blocks_to_xhtml(merged, figures, part["slug"], bilingual)
    title = part["zh"]
    heading = f'<h1>{html.escape(title)}<span class="en">{html.escape(part["en"])}</span></h1>'
    return f'''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="zh-CN" lang="zh-CN">
<head><title>{html.escape(title)}</title><link rel="stylesheet" href="style.css"/></head>
<body><section epub:type="chapter">
{heading}
{body}
{notes_section(part["slug"], numbers, notes)}
</section></body></html>'''


def title_document(bilingual: bool) -> str:
    mode = "中英对照" if bilingual else "中文"
    return f'''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="zh-CN" lang="zh-CN">
<head><title>{TITLE_ZH}</title><link rel="stylesheet" href="style.css"/></head>
<body class="title-page"><section>
<p class="kicker">The White House · OSTP</p>
<h1>{TITLE_ZH}<span class="en">{TITLE_EN}</span></h1>
<p class="subtitle">{mode}版</p>
<p>Michael Kratsios　白宫科学技术政策办公室主任</p>
<p>2026 年 7 月 21 日</p>
<hr/>
<p class="notice">中文译文为非官方译本，供阅读参考；术语、引文、数字与政策措辞请以英文原文（及官方 PDF）为准。</p>
<p class="notice">英文原文来源：<a href="https://www.whitehouse.gov/science/">whitehouse.gov/science</a>；已与官方 PDF 逐词核对。</p>
<p class="notice">人名保留原文；脚注编号沿用官方印刷版（全书 1–185，按章列于章末）。</p>
</section></body></html>'''


def nav_document(parts: list[dict], chapters: dict[str, list[tuple[int, str]]]) -> str:
    items = []
    for part in parts:
        items.append(f'<li><a href="{part["slug"]}.xhtml">{html.escape(part["zh"])}</a>')
        sections = chapters.get(part["slug"], [])
        if sections:
            items.append("<ol>")
            for level, title in sections:
                items.append(f'<li><a href="{part["slug"]}.xhtml#{part["slug"]}-s{level}">{html.escape(title)}</a></li>')
            items.append("</ol>")
        items.append("</li>")
    return f'''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="zh-CN" lang="zh-CN">
<head><title>目录</title><link rel="stylesheet" href="style.css"/></head>
<body><nav epub:type="toc" id="toc"><h1>目录</h1><ol>{"".join(items)}</ol></nav>
<nav epub:type="landmarks" hidden="hidden"><ol>
<li><a epub:type="toc" href="nav.xhtml">目录</a></li>
<li><a epub:type="bodymatter" href="{parts[0]["slug"]}.xhtml">正文</a></li>
</ol></nav></body></html>'''


def build(parts: list[dict], data: dict[str, tuple[list[dict], list[dict]]], figures: list[dict], notes: dict[str, str], bilingual: bool, target: pathlib.Path) -> None:
    work = ROOT / (".epub-build-bi" if bilingual else ".epub-build-zh")
    if work.exists():
        shutil.rmtree(work)
    (work / "META-INF").mkdir(parents=True)
    oebps = work / "OEBPS"
    (oebps / "images").mkdir(parents=True)
    (work / "mimetype").write_text("application/epub+zip", encoding="ascii")
    (work / "META-INF" / "container.xml").write_text(
        '<?xml version="1.0"?><container version="1.0" '
        'xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles>'
        '<rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>'
        "</rootfiles></container>",
        encoding="utf-8",
    )
    (oebps / "style.css").write_text(STYLE, encoding="utf-8")
    (oebps / "title.xhtml").write_text(title_document(bilingual), encoding="utf-8")

    manifest = [
        '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
        '<item id="css" href="style.css" media-type="text/css"/>',
        '<item id="title" href="title.xhtml" media-type="application/xhtml+xml"/>',
    ]
    spine = ['<itemref idref="title"/>']
    chapters: dict[str, list[tuple[int, str]]] = {}
    for part in parts:
        en_blocks, zh_blocks = data[part["slug"]]
        (oebps / f"{part['slug']}.xhtml").write_text(
            part_document(part, en_blocks, zh_blocks, figures, notes, bilingual), encoding="utf-8"
        )
        manifest.append(f'<item id="{part["slug"]}" href="{part["slug"]}.xhtml" media-type="application/xhtml+xml"/>')
        spine.append(f'<itemref idref="{part["slug"]}"/>')
        chapters[part["slug"]] = [
            (index, block["text"])
            for index, block in enumerate(en_blocks)
            if block["type"] == "heading" and block.get("level", 1) > 1
        ]
    (oebps / "nav.xhtml").write_text(nav_document(parts, chapters), encoding="utf-8")

    used_images = sorted({name for entry in figures for name in (entry.get("files") or [entry.get("file")]) if name})
    for name in used_images:
        source = ROOT / "对照稿" / "images" / name
        if source.exists():
            shutil.copyfile(source, oebps / "images" / name)
            media = "image/png" if name.lower().endswith(".png") else "image/jpeg"
            manifest.append(f'<item id="img-{name}" href="images/{name}" media-type="{media}"/>')
        else:
            print(f"  ! missing image file: {name}")

    mode = "中英对照" if bilingual else "中文"
    opf = f'''<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid" xml:lang="zh-CN">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
<dc:identifier id="bookid">{BOOK_ID}-{"bi" if bilingual else "zh"}</dc:identifier>
<dc:title>{TITLE_ZH}（{mode}版）</dc:title>
<dc:title id="en">{TITLE_EN}</dc:title>
<dc:language>zh-CN</dc:language>
<dc:creator>Office of Science and Technology Policy</dc:creator>
<dc:contributor>中文翻译：非官方译本</dc:contributor>
<dc:date>2026-07-21</dc:date>
<dc:source>https://www.whitehouse.gov/science/</dc:source>
<dc:description>白宫科学技术政策办公室 2026 年 7 月 21 日提交总统的报告，{mode}版。脚注编号沿用官方印刷版（1–185）。</dc:description>
<meta property="dcterms:modified">{DATE}T00:00:00Z</meta>
</metadata>
<manifest>{"".join(manifest)}</manifest>
<spine>{"".join(spine)}</spine>
</package>'''
    (oebps / "content.opf").write_text(opf, encoding="utf-8")

    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w") as epub:
        epub.write(work / "mimetype", "mimetype", compress_type=zipfile.ZIP_STORED)
        for path in sorted(work.rglob("*")):
            if path.is_file() and path.name != "mimetype":
                epub.write(path, path.relative_to(work).as_posix(), compress_type=zipfile.ZIP_DEFLATED)
    shutil.rmtree(work)
    print(f"wrote {target.relative_to(ROOT)} ({target.stat().st_size / 1024:.0f} KB, {len(parts)} parts, {len(used_images)} images)")


def main() -> None:
    bilingual_only = "--bilingual-only" in sys.argv
    notes = json.loads(REPORT.read_text(encoding="utf-8"))["footnotes"]
    figures = load_figures()
    data: dict[str, tuple[list[dict], list[dict]]] = {}
    parts: list[dict] = []
    skipped: list[str] = []
    failures: list[str] = []
    for part in PARTS:
        if part["slug"] == "references":
            continue
        en_path = ROOT / "sources" / "en" / f"{part['slug']}.en.md"
        zh_path = ROOT / "sources" / "zh" / f"{part['slug']}.zh.md"
        if not zh_path.exists():
            skipped.append(part["slug"])
            continue
        en_blocks = parse_blocks(en_path)
        zh_blocks = parse_blocks(zh_path)
        problems = validate(part["slug"], en_blocks, zh_blocks)
        if problems:
            failures.append(f"{part['slug']}: {problems[0]}")
            continue
        data[part["slug"]] = (en_blocks, zh_blocks)
        parts.append(part)
    if failures:
        print("ALIGNMENT FAILURES — no EPUB written:")
        for item in failures:
            print("  -", item)
        sys.exit(1)
    if not parts:
        sys.exit("nothing to build")
    build(parts, data, figures, notes, True, OUT_BI)
    if not bilingual_only:
        build(parts, data, figures, notes, False, OUT_ZH)
    if skipped:
        print("MISSING translation (not included):", ", ".join(skipped))


if __name__ == "__main__":
    main()