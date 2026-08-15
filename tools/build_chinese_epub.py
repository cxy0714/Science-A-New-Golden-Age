#!/usr/bin/env python3
"""Build a Chinese machine-translation EPUB from the White House PDF."""

from __future__ import annotations

import html
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "Science-A-New-Golden-Age.pdf"
OUT = ROOT / "科学_一个新的黄金时代_中文机器初译.epub"
CACHE = ROOT / ".translation-cache.json"

CHAPTERS = [
    ("前言、致函与报告摘要", "Front matter, letters, and report summary", "front"),
    ("第一章：引言", "Chapter I: Introduction", "chapter-i"),
    ("第二章：振兴美国科技企业", "Chapter II: Revitalizing America's Science and Technology Enterprise", "chapter-ii"),
    ("第三章：确保美国主导关键与新兴技术", "Chapter III: Ensuring U.S. Dominance in Critical and Emerging Technologies", "chapter-iii"),
    ("第四章：让科技改善所有美国人的生活", "Chapter IV: Ensuring That Science and Technology Better the Lives of All Americans", "chapter-iv"),
    ("第五章：一个新的黄金时代", "Chapter V: A New Golden Age", "chapter-v"),
    ("参考资料与来源", "References & Sources", "references"),
    ("2028 财年研发优先事项备忘录", "FY2028 R&D Priorities Memo", "fy2028"),
]


def extract_pdf() -> str:
    result = subprocess.run(
        ["pdftotext", "-raw", str(PDF), "-"], check=True, text=True,
        encoding="utf-8", stdout=subprocess.PIPE,
    )
    text = result.stdout.replace("\r\n", "\n").replace("\r", "\n")
    # Undo line-break hyphenation while retaining ordinary hyphens.
    text = re.sub(r"(?<=\w)-\n(?=\w)", "", text)
    text = text.replace("\f", "\n\n")
    text = re.sub(r"\n[ivxlcdm]+\n", "\n", text, flags=re.I)
    text = re.sub(r"\n\d+\n(?=(?:Chapter|CHAPTER|Annex|References|SUBJECT:))", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def locate(text: str, needle: str, after: int = 0) -> int:
    found = text.find(needle, after)
    if found < 0:
        raise ValueError(f"Could not locate section marker: {needle!r}")
    return found


def locate_pattern(text: str, pattern: str, after: int = 0) -> int:
    match = re.search(pattern, text[after:], flags=re.S)
    if not match:
        raise ValueError(f"Could not locate section pattern: {pattern!r}")
    return after + match.start()


def split_sections(text: str) -> list[tuple[str, str, str]]:
    # Title-case chapter headers occur in the body; all-caps forms occur in the summary.
    markers = [
        locate_pattern(text, r"Chapter I\s+Introduction"),
        locate_pattern(text, r"Chapter II\s+Revitalizing America.s Science and\s+Technology Enterprise"),
        locate_pattern(text, r"Chapter III\s+Securing U.S. Dominance in Critical and\s+Emerging Technologies"),
        locate_pattern(text, r"Chapter IV\s+Ensuring That Science and Technology Better\s+the Lives of All Americans"),
        locate_pattern(text, r"Chapter V\s+A New Golden Age"),
        locate(text, "1 Vannevar Bush, Science, the Endless Frontier", locate_pattern(text, r"Chapter V\s+A New Golden Age")),
        locate(text, "SUBJECT:", locate(text, "1 Vannevar Bush, Science, the Endless Frontier")),
    ]
    boundaries = [0, *markers, len(text)]
    sections: list[tuple[str, str, str]] = []
    for (title, english, slug), start, end in zip(CHAPTERS, boundaries, boundaries[1:]):
        body = text[start:end].strip()
        # Remove the repeated body heading; title metadata retains it cleanly.
        if slug != "front":
            body = re.sub(r"^(?:Chapter [IVX]+\n.*?\n){1,2}", "", body, count=1, flags=re.S)
        sections.append((title, english, slug, body))
    return sections


def load_cache() -> dict[str, str]:
    if not CACHE.exists():
        return {}
    return json.loads(CACHE.read_text(encoding="utf-8"))


def save_cache(cache: dict[str, str]) -> None:
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def translate_batch(source: str) -> str:
    query = urllib.parse.urlencode({
        "client": "gtx", "sl": "en", "tl": "zh-CN", "dt": "t", "q": source,
    })
    request = urllib.request.Request(
        "https://translate.googleapis.com/translate_a/single?" + query,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return "".join(part[0] for part in payload[0] if part and part[0])


def translate_paragraphs(source: str, cache: dict[str, str]) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", source) if p.strip()]
    pending = [p for p in paragraphs if p not in cache]
    batches: list[list[str]] = []
    while pending:
        batch: list[str] = []
        size = 0
        while pending and len(pending[0]) <= 3600 and size + len(pending[0]) + 2 <= 3400:
            paragraph = pending.pop(0)
            batch.append(paragraph)
            size += len(paragraph) + 2
        if batch:
            batches.append(batch)
        else:
            # Rare oversized paragraphs are translated in sentence-sized pieces.
            paragraph = pending.pop(0)
            pieces = []
            remainder = paragraph
            while len(remainder) > 3400:
                cut = max(remainder.rfind(". ", 0, 3400), remainder.rfind(" ", 0, 3400))
                pieces.append(remainder[:cut + 1])
                remainder = remainder[cut + 1:].lstrip()
            pieces.append(remainder)
            cache[paragraph] = "".join(translate_batch(piece) for piece in pieces)
    completed = 0
    def do_batch(batch: list[str]) -> tuple[list[str], str]:
        return batch, translate_batch("\n\n".join(batch))
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = [pool.submit(do_batch, batch) for batch in batches]
        for future in as_completed(futures):
            batch, translated = future.result()
            translated_parts = [p.strip() for p in re.split(r"\n\s*\n", translated) if p.strip()]
            if len(translated_parts) == len(batch):
                for source_part, translated_part in zip(batch, translated_parts):
                    cache[source_part] = translated_part
                completed += len(batch)
            else:
                # Preserve correctness over throughput if a provider changes separator behavior.
                for source_part in batch:
                    cache[source_part] = translate_batch(source_part)
                    completed += 1
            if completed % 20 < len(batch) + 1:
                save_cache(cache)
                print(f"Translated {completed}/{len(paragraphs)} new paragraphs", flush=True)
    save_cache(cache)
    return [cache[p] for p in paragraphs]


def xhtml_document(title: str, english: str, paragraphs: list[str], source_page: str) -> str:
    content = "\n".join(f"<p>{html.escape(p)}</p>" for p in paragraphs)
    return f'''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="zh-CN" lang="zh-CN">
<head><title>{html.escape(title)}</title><link rel="stylesheet" href="style.css" /></head>
<body><section>
<h1>{html.escape(title)}</h1>
<p class="english">{html.escape(english)}</p>
<p class="source">原文来源：White House, <i>Science: A New Golden Age</i>（2026 年 7 月）。{source_page}</p>
{content}
</section></body></html>'''


def title_page() -> str:
    return '''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="zh-CN" lang="zh-CN">
<head><title>科学：一个新的黄金时代</title><link rel="stylesheet" href="style.css" /></head>
<body class="title-page"><section>
<p class="kicker">美国白宫报告</p>
<h1>科学：一个新的黄金时代</h1>
<p class="subtitle">致总统的报告</p>
<p>Michael Kratsios<br/>白宫科学技术政策办公室主任</p>
<p>2026 年 7 月</p>
<hr />
<p class="notice">中文机器初译，非官方译本。术语、引文、数字和政策措辞请以英文官方 PDF 为准。</p>
<p class="notice">原文：<a href="https://www.whitehouse.gov/science/">whitehouse.gov/science</a></p>
</section></body></html>'''


def nav_document() -> str:
    entries = [f'<li><a href="{slug}.xhtml">{html.escape(title)}</a></li>' for title, _, slug in CHAPTERS]
    return '''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html><html xmlns="http://www.w3.org/1999/xhtml" xml:lang="zh-CN"><head><title>目录</title></head>
<body><nav epub:type="toc" id="toc" xmlns:epub="http://www.idpf.org/2007/ops"><h1>目录</h1><ol>''' + "".join(entries) + "</ol></nav></body></html>"


STYLE = '''body { font-family: serif; line-height: 1.65; margin: 7%; color: #1b1b1b; }
h1 { font-size: 1.65em; line-height: 1.3; margin: 0 0 0.3em; }
p { margin: 0 0 0.9em; text-align: justify; }
.english, .source, .notice { color: #555; font-size: .88em; }
.english { font-style: italic; } .title-page { text-align: center; padding-top: 20%; }
.title-page p { text-align: center; } .title-page h1 { font-size: 2em; }
.kicker { letter-spacing: .1em; } .subtitle { font-size: 1.2em; }
a { color: #254f75; } hr { margin: 2em 0; }
'''


def build_epub(sections: list[tuple[str, str, str, list[str]]]) -> None:
    work = ROOT / ".epub-build"
    if work.exists():
        shutil.rmtree(work)
    (work / "META-INF").mkdir(parents=True)
    oebps = work / "OEBPS"
    oebps.mkdir()
    (work / "mimetype").write_text("application/epub+zip", encoding="ascii")
    (work / "META-INF" / "container.xml").write_text(
        '''<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>''',
        encoding="utf-8",
    )
    (oebps / "style.css").write_text(STYLE, encoding="utf-8")
    (oebps / "title.xhtml").write_text(title_page(), encoding="utf-8")
    (oebps / "nav.xhtml").write_text(nav_document(), encoding="utf-8")
    manifest = ['<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>', '<item id="css" href="style.css" media-type="text/css"/>', '<item id="title" href="title.xhtml" media-type="application/xhtml+xml"/>']
    spine = ['<itemref idref="title"/>']
    for title, english, slug, paragraphs in sections:
        (oebps / f"{slug}.xhtml").write_text(xhtml_document(title, english, paragraphs, "对应官方 PDF 正文。"), encoding="utf-8")
        manifest.append(f'<item id="{slug}" href="{slug}.xhtml" media-type="application/xhtml+xml"/>')
        spine.append(f'<itemref idref="{slug}"/>')
    opf = f'''<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid" xml:lang="zh-CN">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:identifier id="bookid">urn:uuid:science-new-golden-age-zh-machine-translation</dc:identifier><dc:title>科学：一个新的黄金时代</dc:title><dc:language>zh-CN</dc:language><dc:creator>Michael Kratsios</dc:creator><dc:contributor>Machine translation</dc:contributor><dc:date>2026-08-15</dc:date><dc:source>https://www.whitehouse.gov/science/</dc:source><meta property="dcterms:modified">2026-08-15T00:00:00Z</meta></metadata>
<manifest>{''.join(manifest)}</manifest><spine>{''.join(spine)}</spine></package>'''
    (oebps / "content.opf").write_text(opf, encoding="utf-8")
    with zipfile.ZipFile(OUT, "w") as epub:
        epub.write(work / "mimetype", "mimetype", compress_type=zipfile.ZIP_STORED)
        for path in sorted(work.rglob("*")):
            if path.is_file() and path.name != "mimetype":
                epub.write(path, path.relative_to(work).as_posix(), compress_type=zipfile.ZIP_DEFLATED)
    shutil.rmtree(work)


def main() -> None:
    if not PDF.exists():
        sys.exit(f"Missing source PDF: {PDF}")
    cache = load_cache()
    source_sections = split_sections(extract_pdf())
    translated_sections = []
    for title, english, slug, source in source_sections:
        print(f"Translating: {title}", flush=True)
        if slug == "references":
            paragraphs = [
                "以下保留官方 PDF 的英文书目信息与链接，以避免机器翻译改变作者名、题名、版本信息或 URL。",
                *[p.strip() for p in re.split(r"\n\s*\n", source) if p.strip()],
            ]
        else:
            paragraphs = translate_paragraphs(source, cache)
        translated_sections.append((title, english, slug, paragraphs))
    build_epub(translated_sections)
    print(f"Created {OUT}", flush=True)


if __name__ == "__main__":
    main()
