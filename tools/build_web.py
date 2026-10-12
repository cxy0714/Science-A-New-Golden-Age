#!/usr/bin/env python3
"""Build the static HTML edition of the report (a Quarto book) into docs/.

Input is exactly what the EPUB is built from, through the same alignment gate
(see tools/build_bilingual.py):

  sources/en/<slug>.en.md      English, official web edition, PDF-checked
  sources/zh/<slug>.zh.md      Chinese translation, block-for-block mirror
  sources/report.json          the 185 printed-edition endnotes
  对照稿/images/manifest.json  figures (rendered from the official PDF vectors)

Output:

  web/<slug>.qmd               one generated page per part
  web/index.qmd                 cover, how to read, contents, downloads
  web/99-colophon.qmd           editorial conventions and provenance
  web/_quarto.yml               book structure (generated, keeps order in sync)
  web/images/*.png              the figures referenced by the text
  docs/                         the rendered site (quarto render)

Body text is emitted as passthrough HTML (```{=html}) so that pandoc cannot
rewrite it: Quarto honours --, ..., $ and emphasis only inside such blocks,
while Markdown headings stay Markdown so they reach the TOC and the search
index. Each language sits in its own .en / .zh element, and a switch in the
sidebar flips data-lang-mode on <html> (see web/styles.css).

Usage:
  python tools/build_web.py              # generate pages, then render into docs/
  python tools/build_web.py --no-render  # generate the project only
"""

from __future__ import annotations

import collections
import html
import json
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_bilingual import (  # noqa: E402
    PARTS,
    REPORT,
    body_skip_indices,
    figures_for,
    load_figures,
    markers,
    merge_notes,
    parse_blocks,
    validate,
)

WEB = ROOT / "web"
DOCS = ROOT / "docs"
IMAGE_SOURCE = ROOT / "对照稿" / "images"

SITE_TITLE = "科学：一个新的黄金时代"
SITE_SUBTITLE = "Science: A New Golden Age · 中英对照"
SITE_AUTHOR = "白宫科学技术政策办公室（OSTP）报告 · 中文为非官方重译"
SITE_DATE = "2026-07-21"
REPO_URL = "https://github.com/cxy0714/Science-A-New-Golden-Age"
REPO_BRANCH = "main"
REPO_SUBDIR = "web"
OFFICIAL_WEB = "https://www.whitehouse.gov/science/"
OFFICIAL_PDF = "https://www.whitehouse.gov/wp-content/uploads/2026/07/Science-A-New-Golden-Age.pdf"

# Sidebar / page titles: the part titles as printed in the book.
LABELS = {
    "front": "前言：致函与报告摘要",
    "annex-fy2028": "附录：2028 财年研发优先事项备忘录",
}
NOTES_LABEL = "本章脚注 · Notes（沿用官方印刷版编号）"
NOTES_LABEL_LOCAL = "本章注释 · Notes（备忘录自身编号）"

NOTE_REF = re.compile(r"\[\^(\d+)\]")
MD_LINK = re.compile(r"\[([^\]^]+)\]\((https?://[^)\s]+)\)")
CODE = re.compile(r"`([^`]+)`")
BOLD = re.compile(r"\*\*([^*]+)\*\*")
ITALIC = re.compile(r"\*([^*]+)\*")
SEPARATOR_CELL = re.compile(r":?-{2,}:?")


def esc(text: str, quote: bool = False) -> str:
    return html.escape(text, quote=quote)


def yaml_value(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def label(part: dict) -> str:
    return LABELS.get(part["slug"], part["zh"])


class Page:
    """One book page: Markdown headings interleaved with passthrough HTML."""

    def __init__(self, slug: str) -> None:
        self.slug = slug
        self.out: list[str] = []
        self.raw: list[str] = []
        self.ids: collections.Counter[str] = collections.Counter()
        self.first_ref: dict[str, str] = {}
        self.current = ""
        self.stray_asterisks = 0
        self.refs = 0

    # -- primitives ---------------------------------------------------------
    def html(self, *lines: str) -> None:
        self.raw.extend(lines)

    def flush(self) -> None:
        if self.raw:
            self.out.append("```{=html}")
            self.out.extend(self.raw)
            self.out.append("```")
            self.out.append("")
            self.raw = []

    def heading(self, level: int, title: str) -> None:
        self.flush()
        self.out.append("#" * level + " " + title)
        self.out.append("")

    def text(self, value: str, side: str) -> str:
        """Markdown subset -> HTML. Callers wrap the result in an element."""
        out = esc(value)
        out = NOTE_REF.sub(lambda match: self.noteref(match.group(1), side), out)
        out = MD_LINK.sub(lambda match: f'<a href="{match.group(2)}">{match.group(1)}</a>', out)
        out = CODE.sub(lambda match: f"<code>{match.group(1)}</code>", out)
        out = BOLD.sub(lambda match: f"<strong>{match.group(1)}</strong>", out)
        out = ITALIC.sub(lambda match: f"<em>{match.group(1)}</em>", out)
        self.stray_asterisks += out.count("*")
        return out

    def noteref(self, number: str, side: str) -> str:
        base = f"fnref-{self.slug}-{number}-{side}"
        seen = self.ids[base]
        self.ids[base] += 1
        ident = base if seen == 0 else f"{base}-{seen + 1}"
        if number not in self.first_ref and self.current:
            self.first_ref[number] = self.current
        self.refs += 1
        return (
            f'<a class="noteref" id="{ident}" href="#fn-{self.slug}-{number}" '
            f'role="doc-noteref" title="脚注 {number}"><sup>{number}</sup></a>'
        )

    # -- blocks -------------------------------------------------------------
    def pair(self, pid: str, en_inner: str, zh_inner: str, tag: str = "p", cls: str = "pair") -> None:
        self.html(f'<div class="{cls}">')
        self.html(f'<div class="en" id="{pid}-en"><{tag}>{en_inner}</{tag}></div>')
        self.html(f'<div class="zh" id="{pid}-zh"><{tag}>{zh_inner}</{tag}></div>')
        self.html("</div>")

    def notes_section(self, numbers: list[int], notes: dict[str, str], label_text: str) -> None:
        if not numbers:
            return
        self.heading(2, label_text)
        items = []
        for number in numbers:
            body = self.text(notes[str(number)], "note")
            target = self.first_ref.get(str(number))
            back = (
                f' <a class="note-back" data-target="{target}" href="#{target}-en" title="返回正文">↩</a>'
                if target
                else ""
            )
            items.append(f'<li id="fn-{self.slug}-{number}" value="{number}">{body}{back}</li>')
        self.html('<div class="chapter-notes">', '<ol class="notes">', *items, "</ol>", "</div>")

    def finish(self) -> str:
        self.flush()
        return "\n".join(self.out).rstrip() + "\n"


def render_part(part: dict, en_blocks: list[dict], zh_blocks: list[dict], notes: dict[str, str], figures: list[dict]) -> tuple[str, dict]:
    page = Page(part["slug"])
    skip = body_skip_indices(en_blocks)
    used = sorted({int(n) for block in en_blocks for n in markers(block["text"])})
    missing = [n for n in used if str(n) not in notes]
    if missing:
        raise SystemExit(f"{part['slug']}: no endnote text for {missing}")

    index = 0
    counted = 0
    images: list[str] = []
    while index < len(en_blocks):
        if index in skip:
            index += 1
            continue
        en, zh = en_blocks[index], zh_blocks[index]
        kind = en["type"]
        pid = f"p-{part['slug']}-{index}"
        page.current = pid
        counted += 1

        if kind == "heading":
            index += 1
            if en.get("level") == 1:  # the part title lives in the page title block
                continue
            page.heading(min(3, max(2, en["level"] - 1)), zh["text"])
            page.html(f'<div class="en h-en"><p>{page.text(en["text"], "en")}</p></div>')
            continue

        if kind == "list":
            en_items: list[str] = []
            zh_items: list[str] = []
            while index < len(en_blocks) and en_blocks[index]["type"] == "list" and index not in skip:
                item_id = f"p-{part['slug']}-{index}"
                page.current = item_id
                en_items.append(f'<li id="{item_id}-en">{page.text(en_blocks[index]["text"], "en")}</li>')
                zh_items.append(f'<li id="{item_id}-zh">{page.text(zh_blocks[index]["text"], "zh")}</li>')
                index += 1
            page.html('<div class="pair">')
            page.html('<div class="en"><ul>', *en_items, "</ul></div>")
            page.html('<div class="zh"><ul>', *zh_items, "</ul></div>")
            page.html("</div>")
            continue

        if kind == "paragraph" and en["text"].startswith("|"):
            en_rows: list[list[str]] = []
            zh_rows: list[list[str]] = []
            while index < len(en_blocks) and en_blocks[index]["text"].startswith("|"):
                en_rows.append([cell.strip() for cell in en_blocks[index]["text"].strip("|").split("|")])
                zh_rows.append([cell.strip() for cell in zh_blocks[index]["text"].strip("|").split("|")])
                index += 1
            page.html('<div class="pair table-pair">')

            def table(rows: list[list[str]], side: str, anchor: str) -> None:
                body = [row for row in rows if not all(SEPARATOR_CELL.fullmatch(cell) for cell in row)]
                if not body:
                    return
                head, *rest = body
                cells = "".join(f"<th>{page.text(cell, side)}</th>" for cell in head)
                page.html(f'<div class="{side}" id="{anchor}-{side}">', f'<table class="data"><thead><tr>{cells}</tr></thead><tbody>')
                for row in rest:
                    page.html("<tr>" + "".join(f"<td>{page.text(cell, side)}</td>" for cell in row) + "</tr>")
                page.html("</tbody></table>", "</div>")

            table(en_rows, "en", pid)
            table(zh_rows, "zh", pid)
            page.html("</div>")
            continue

        index += 1

        if kind == "stat":
            page.html('<div class="stat">')
            page.html(f'<div class="en" id="{pid}-en"><p>{page.text(en["text"], "en")}</p></div>')
            page.html(f'<div class="zh" id="{pid}-zh"><p>{page.text(zh["text"], "zh")}</p></div>')
            page.html("</div>")
        elif kind == "caption":
            entries = figures_for(figures, part["slug"], en["text"])
            names = [name for entry in entries for name in (entry.get("files") or [entry.get("file")]) if name]
            alternative = re.sub(r"\[\^\d+\]|[*`]", "", zh["text"]).strip()
            page.html(f'<div class="pair figure-pair">')
            page.html(f'<div class="en" id="{pid}-en"><p class="figcap">{page.text(en["text"], "en")}</p></div>')
            page.html(f'<div class="zh" id="{pid}-zh"><p class="figcap">{page.text(zh["text"], "zh")}</p></div>')
            if names:
                images.extend(names)
                tags = "".join(
                    f'<img src="images/{name}" alt="{esc(alternative, quote=True)}" loading="lazy"/>' for name in names
                )
                page.html(f'<figure class="figimg">{tags}</figure>')
            page.html("</div>")
        elif kind == "subhead":
            page.html('<div class="pair subhead">')
            page.html(f'<div class="en" id="{pid}-en"><p>{page.text(en["text"], "en")}</p></div>')
            page.html(f'<div class="zh" id="{pid}-zh"><p>{page.text(zh["text"], "zh")}</p></div>')
            page.html("</div>")
        else:
            page.pair(pid, page.text(en["text"], "en"), page.text(zh["text"], "zh"))

    label_text = NOTES_LABEL_LOCAL if part.get("notes_label") else NOTES_LABEL
    page.notes_section(used, notes, label_text)

    head = (
        "---\n"
        f"title: {yaml_value(label(part))}\n"
        f"subtitle: {yaml_value(part['en'])}\n"
        "---\n\n"
    )
    stats = {
        "slug": part["slug"],
        "label": label(part),
        "en": part["en"],
        "blocks": counted,
        "notes": len(used),
        "refs": page.refs,
        "images": sorted(set(images)),
        "stray_asterisks": page.stray_asterisks,
    }
    return head + page.finish(), stats


def index_page(rows: list[dict]) -> str:
    contents = "\n".join(
        f"| [{row['label']}]({row['slug']}.qmd) | {row['blocks']} 段"
        + (f"，脚注 {row['notes']} 条" if row["notes"] else "")
        + " |"
        for row in rows
    )
    return f"""---
title: {yaml_value(SITE_TITLE)}
subtitle: {yaml_value(SITE_SUBTITLE)}
---

【{SITE_AUTHOR}】 · {SITE_DATE}

本书是白宫科学技术政策办公室（OSTP）2026 年 7 月 21 日提交总统的报告 *Science: A New Golden Age: A Report to the President* 的**中英对照**电子书。英文取自官方网页版并与官方 PDF 逐词核对；中文为人工重译，非官方译本。

## 怎么读

每一段先给英文原文，紧接中文译文。左侧栏搜索框下方的 **显示** 开关可以切换三种模式：

| 模式 | 效果 |
| --- | --- |
| 双语 | 英文在上（淡色、左侧细线），中文在下，适合对照细读 |
| 中文 | 只留中文，适合通读 |
| English | 只留英文，适合核对原文 |

快捷键：`Alt` + `1` / `2` / `3`；选择会记住。右侧「本页目录」可在本章内跳转，左上角搜索框检索全书（中英皆可），右上角可切换浅色／深色，点击图表可放大。带编号的上标是脚注，按**官方印刷版**编号（全书 1–185），点击跳到章末注释，注释末尾的 ↩ 回到原文。

## 目录

| 篇目 | 篇幅 |
| --- | --- |
{contents}

另有 [体例、来源与引用说明](99-colophon.qmd)。

## 下载与原文

| 文件 | 说明 |
| --- | --- |
| [中英对照 EPUB]({REPO_URL}/raw/{REPO_BRANCH}/科学_一个新的黄金时代_中英对照.epub) | 适合 Apple Books、Calibre、Kobo 等阅读器离线阅读 |
| [纯中文 EPUB]({REPO_URL}/raw/{REPO_BRANCH}/科学_一个新的黄金时代_中文.epub) | 同一译文，去掉英文对照 |
| [官方英文 PDF]({OFFICIAL_PDF}) | 引用与核对请以官方原文为准 |
| [官方网页版]({OFFICIAL_WEB}) | whitehouse.gov/science |
| [项目仓库]({REPO_URL}) | 生成脚本、中英对照 Markdown、校订记录 |

## 说明

中文译文为非官方译本，供阅读参考。政策措辞、数字、专有名词、脚注与引文请以英文原文（及官方 PDF）为准；引用报告时应引用原文，而不是本电子书。
"""


def colophon_page() -> str:
    return f"""---
title: "体例、来源与引用说明"
subtitle: "Editorial Conventions, Sources and Citation"
---

本书的英文底本、中文译文与脚注编号都经过逐块校验：段数、块类型、章节编号、脚注编号四项中任何一项不一致，生成脚本即拒绝出书。以下说明体例。

## 底本与来源

| 内容 | 来源 |
| --- | --- |
| 英文正文 | 官方网页版 whitehouse.gov/science，逐词与官方 PDF 核对 |
| 2028 财年备忘录 | 该备忘录自身的官方 PDF（单行本），另附其自身编号的 5 条注释 |
| 中文译文 | 本项目人工重译，非官方译本 |
| 图 1 至图 4 | 官方 PDF 的矢量原图渲染，非网页版位图 |

## 体例

- **人名保留原文**：`Vannevar Bush`、`Donald Stokes`、`Shannon`、`Pasteur`、`Trump` 等不音译；人名派生的术语保留原文并加通译提示（如 `Pasteur 象限`）。
- **机构缩写保留原文**（NSF、NIH、DOE、DARPA、OMB、OSTP 等），首次出现给中文全称。
- **参考文献保留英文**，不改动作者、题名、版本与 URL。
- **脚注编号沿用官方印刷版**：全书 1 至 185 连续，按章列于章末。官方网页版正文的角标数字整体偏移 +1，且注释表漏排了印刷版第 13 条，本项目以网页列表锚点还原为印刷版编号。附录备忘录的注释为它自身编号的 1 至 5 条。
- 中文引文用「」，书名用《》；中拉之间留一个空格。

## 校订情况

全书经过两轮：先逐块翻译，再由独立的校对代理逐章对照英文复核，只改真错（漏译、加译、数字与专名错误、术语不一致、翻译腔），改完必须重跑对齐校验。累计修正 190 余处，例如「城市规模的芯片交响乐团协同工作」改为「城市规模的芯片如同交响乐团般协同运作」，「最优秀的大脑」改为「最优秀的人才」。

## 引用方式

这是非官方译本，**请勿用它代替原文引用**。引用报告时请引用官方英文原文：

> Office of Science and Technology Policy, *Science: A New Golden Age: A Report to the President* (Washington, DC: The White House, July 21, 2026).

## 生成与版本

本网页版由仓库中的 `tools/build_web.py` 生成（Quarto book），与 EPUB 同出一源：`sources/en`、`sources/zh` 与 `sources/report.json`。图表取自 `对照稿/images/`。全书英文约 3.6 万词，中文约 7.7 万字。

仓库：[{REPO_URL}]({REPO_URL}) · 官方原文：[{OFFICIAL_WEB}]({OFFICIAL_WEB})
"""


def quarto_config(slugs: list[str]) -> str:
    chapters = "\n".join(f"    - {name}.qmd" for name in ["index"] + slugs + ["99-colophon"])
    return f"""# 由 tools/build_web.py 生成，请勿手工修改（改结构请改脚本里的 PARTS / LABELS）。
project:
  type: book
  output-dir: ../docs
  resources:
    - images/*.png

book:
  title: {yaml_value(SITE_TITLE)}
  subtitle: {yaml_value(SITE_SUBTITLE)}
  author: {yaml_value(SITE_AUTHOR)}
  date: {yaml_value(SITE_DATE)}
  repo-url: {REPO_URL}
  repo-branch: {REPO_BRANCH}
  repo-subdir: {REPO_SUBDIR}
  repo-actions: [edit]
  sharing: []
  search:
    location: sidebar
    type: textbox
    limit: 40
  page-navigation: true
  back-to-top-navigation: true
  sidebar:
    style: docked
    collapse-level: 1
    border: true
  chapters:
{chapters}

lang: zh

format:
  html:
    theme:
      light: cosmo
      dark: darkly
    css: styles.css
    number-sections: false
    toc: true
    toc-depth: 2
    toc-title: "本页目录"
    anchor-sections: true
    smooth-scroll: true
    code-copy: false
    fig-align: center
    link-external-newwindow: false
    footnotes-hover: false
    citations-hover: false
    include-in-header: lang-mode-head.html
    include-after-body: lang-toggle.html
"""


def copy_images(names: list[str], target: pathlib.Path) -> int:
    target.mkdir(parents=True, exist_ok=True)
    copied = 0
    for name in names:
        source = IMAGE_SOURCE / name
        if not source.exists():
            print(f"  ! missing figure file: {source.relative_to(ROOT)}")
            continue
        shutil.copyfile(source, target / name)
        copied += 1
    return copied


def render_site() -> None:
    # docs/ is entirely generated: clear it first so that assets from an earlier
    # render (renamed theme bundles, removed pages) cannot linger in the site.
    if DOCS.exists():
        shutil.rmtree(DOCS)
    print("\n$ quarto render (web/)")
    result = subprocess.run(
        ["quarto", "render"],
        cwd=str(WEB),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    tail = "\n".join((result.stdout or "").strip().splitlines()[-12:])
    if tail:
        print(tail)
    if result.returncode != 0:
        print((result.stderr or "").strip()[-4000:])
        raise SystemExit(f"quarto render failed (exit {result.returncode})")


def main() -> None:
    do_render = "--no-render" not in sys.argv
    notes = json.loads(REPORT.read_text(encoding="utf-8"))["footnotes"]
    figures = load_figures()
    if not WEB.exists():
        raise SystemExit("web/ is missing: styles.css, lang-mode-head.html and lang-toggle.html live there")

    WEB.mkdir(exist_ok=True)
    rows: list[dict] = []
    slugs: list[str] = []
    used_images: set[str] = set()
    failures: list[str] = []

    for part in PARTS:
        en_path = ROOT / "sources" / "en" / f"{part['slug']}.en.md"
        zh_path = ROOT / "sources" / "zh" / f"{part['slug']}.zh.md"
        if not zh_path.exists():
            failures.append(f"{part['slug']}: no translation")
            continue
        en_blocks = parse_blocks(en_path)
        zh_blocks = parse_blocks(zh_path)
        problems = validate(part["slug"], en_blocks, zh_blocks)
        if problems:
            failures.append(f"{part['slug']}: {problems[0]}")
            continue
        part_notes = merge_notes(en_blocks, notes)
        body, stats = render_part(part, en_blocks, zh_blocks, part_notes, figures)
        (WEB / f"{part['slug']}.qmd").write_text(body, encoding="utf-8")
        slugs.append(part["slug"])
        rows.append(stats)
        used_images.update(stats["images"])

    if failures:
        print("ALIGNMENT FAILURES, no site written:")
        for item in failures:
            print("  -", item)
        raise SystemExit(1)

    (WEB / "index.qmd").write_text(index_page(rows), encoding="utf-8")
    (WEB / "99-colophon.qmd").write_text(colophon_page(), encoding="utf-8")
    (WEB / "_quarto.yml").write_text(quarto_config(slugs), encoding="utf-8")

    print(f"generated {len(slugs)} pages + index + colophon in web/")
    for row in rows:
        note = f", {row['notes']} notes ({row['refs']} refs)" if row["notes"] else ""
        images = f", images: {', '.join(row['images'])}" if row["images"] else ""
        stray = f"  !! stray asterisks: {row['stray_asterisks']}" if row["stray_asterisks"] else ""
        print(f"  {row['slug']:14s} {row['blocks']:3d} blocks{note}{images}{stray}")
    copied = copy_images(sorted(used_images), WEB / "images")
    print(f"figures: {copied} file(s) copied into web/images/")

    if do_render:
        render_site()
        copied = copy_images(sorted(used_images), DOCS / "images")
        missing = [name for name in ("index.html", "search.json") if not (DOCS / name).exists()]
        pages = [slug for slug in slugs if not (DOCS / f"{slug}.html").exists()]
        print(f"\ndocs/: {copied} figure(s), {len(slugs)} chapter page(s)")
        if missing:
            raise SystemExit(f"render produced no {missing}")
        if pages:
            raise SystemExit(f"render produced no page for {pages}")
        print("site ready: docs/index.html")


if __name__ == "__main__":
    main()