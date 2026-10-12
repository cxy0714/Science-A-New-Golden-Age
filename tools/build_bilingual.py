#!/usr/bin/env python3
"""Assemble validated bilingual (English/Chinese) files for each translated part.

Pairs `sources/en/<slug>.en.md` (extracted from the official web edition and
cross-checked against the printed PDF) with `sources/zh/<slug>.zh.md` block by
block. Refuses to emit a part unless paragraph sequence, block types, section
numbers, list-item counts and endnote markers all line up.

Usage:
  python tools/build_bilingual.py                 # all parts that have a translation
  python tools/build_bilingual.py front chapter-01
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
REPORT = ROOT / "sources" / "report.json"
OUT_DIR = ROOT / "对照稿"

PARTS = [
    {
        "slug": "front",
        "zh": "前言、致函与报告摘要",
        "en": "Front Matter: Letters and Summary",
        "out": "00_前言_致函与报告摘要.md",
    },
    {
        "slug": "chapter-01",
        "zh": "第一章 引言",
        "en": "Chapter I: Introduction",
        "out": "01_第一章_引言.md",
    },
    {
        "slug": "chapter-02",
        "zh": "第二章 振兴美国科学技术事业",
        "en": "Chapter II: Revitalizing America's Science and Technology Enterprise",
        "out": "02_第二章_振兴美国科学技术事业.md",
    },
    {
        "slug": "chapter-03",
        "zh": "第三章 确保美国在关键与新兴技术上的主导地位",
        "en": "Chapter III: Ensuring U.S. Dominance in Critical and Emerging Technologies",
        "out": "03_第三章_确保美国在关键与新兴技术上的主导地位.md",
    },
    {
        "slug": "chapter-04",
        "zh": "第四章 让科学技术改善所有美国人的生活",
        "en": "Chapter IV: Ensuring That Science and Technology Better the Lives of All Americans",
        "out": "04_第四章_让科学技术改善所有美国人的生活.md",
    },
    {
        "slug": "chapter-05",
        "zh": "第五章 一个新的黄金时代",
        "en": "Chapter V: A New Golden Age",
        "out": "05_第五章_一个新的黄金时代.md",
    },
    {
        "slug": "annex-fy2028",
        "zh": "2028 财年研发优先事项备忘录",
        "en": "Annex: FY2028 R&D Priorities Memo",
        "out": "06_2028财年研发优先事项备忘录.md",
    },
]

HEADER = """> 中英对照稿 · 《科学：一个新的黄金时代》（*Science: A New Golden Age*）
> 英文取自白宫官方网页版，中文为人工重译。体例见 `sources/STYLE.md`；人名保留原文；
> `[^n]` 沿用官方印刷版脚注编号。[^n] 定义见各章末尾，或全书合并稿的注释部分。
"""


def parse_blocks(path: pathlib.Path) -> list[dict]:
    blocks: list[dict] = []
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("<!--"):
            continue
        if line.startswith("#"):
            blocks.append({"type": "heading", "level": len(line) - len(line.lstrip("#")), "text": line.lstrip("# ").strip(), "line": number})
        elif re.fullmatch(r"\*\*[^*]+\*\*", line):
            blocks.append({"type": "subhead", "text": line.strip("*").strip(), "line": number})
        elif line.startswith(">"):
            blocks.append({"type": "stat", "text": line.lstrip("> ").strip(), "line": number})
        elif re.fullmatch(r"\*[^*].*\*", line):
            blocks.append({"type": "caption", "text": line.strip("*").strip(), "line": number})
        elif line.startswith("- "):
            blocks.append({"type": "list", "text": line[2:].strip(), "line": number})
        else:
            blocks.append({"type": "paragraph", "text": line, "line": number})
    return blocks


def markers(text: str) -> list[str]:
    return re.findall(r"\[\^(\d+)\]", text)


def validate(slug: str, en_blocks: list[dict], zh_blocks: list[dict]) -> list[str]:
    problems: list[str] = []
    if len(en_blocks) != len(zh_blocks):
        problems.append(f"block count differs: en={len(en_blocks)} zh={len(zh_blocks)}")
        # Report the first divergence to make the fix obvious.
        for index, (en, zh) in enumerate(zip(en_blocks, zh_blocks)):
            if en["type"] != zh["type"]:
                problems.append(f"  first divergence at block {index + 1}: en={en['type']} zh={zh['type']}")
                problems.append(f"    en: {en['text'][:80]}")
                problems.append(f"    zh: {zh['text'][:80]}")
                break
        return problems
    for index, (en, zh) in enumerate(zip(en_blocks, zh_blocks)):
        label = f"block {index + 1}"
        if en["type"] != zh["type"]:
            problems.append(f"{label}: type mismatch (en={en['type']}, zh={zh['type']})\n    en: {en['text'][:80]}\n    zh: {zh['text'][:80]}")
            continue
        if en["type"] == "heading":
            en_num = re.match(r"^[IVX]+\.\d+", en["text"])
            zh_num = re.match(r"^[IVX]+\.\d+", zh["text"])
            if bool(en_num) != bool(zh_num) or (en_num and en_num.group(0) != zh_num.group(0)):
                problems.append(f"{label}: section number mismatch (en={en['text'][:40]} zh={zh['text'][:40]})")
            continue
        if markers(en["text"]) != markers(zh["text"]):
            problems.append(f"{label}: endnote markers differ\n    en={markers(en['text'])}\n    zh={markers(zh['text'])}")
    return problems


def load_figures() -> list[dict]:
    manifest = OUT_DIR / "images" / "manifest.json"
    if not manifest.exists():
        return []
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else data.get("figures", [])


def figures_for(manifest: list[dict], slug: str, caption: str) -> list[dict]:
    """Manifest entries whose figure label (e.g. "Figure 1 (left panel)") names a figure
    mentioned in this caption."""
    found: list[dict] = []
    for entry in manifest:
        if entry.get("slug") and entry["slug"] != slug:
            continue
        label = re.match(r"(Figure|Table)\s+(\d+)", str(entry.get("figure", "")), re.I)
        if label and f"{label.group(1).lower()} {label.group(2)}" in caption.lower():
            found.append(entry)
    return found


def render(
    part: dict,
    en_blocks: list[dict],
    zh_blocks: list[dict],
    notes: dict[str, str],
    figures: list[dict] | None = None,
    image_prefix: str = "images/",
    level_shift: int = 0,
    title_level: int = 1,
    notes_heading_level: int = 2,
) -> str:
    used = sorted({int(n) for block in en_blocks for n in markers(block["text"])})
    lines = [HEADER.rstrip(), "", f"{'#' * title_level} {part['zh']} · *{part['en']}*", ""]
    first_heading_seen = False
    index = 0
    while index < len(en_blocks):
        en, zh = en_blocks[index], zh_blocks[index]
        kind = en["type"]
        # Markdown table rows are paragraph-typed blocks; they must stay on consecutive
        # lines or the renderer stops seeing a table.
        if kind == "paragraph" and en["text"].startswith("|"):
            english_rows: list[str] = []
            chinese_rows: list[str] = []
            while index < len(en_blocks) and en_blocks[index]["text"].startswith("|"):
                english_rows.append(en_blocks[index]["text"])
                chinese_rows.append(zh_blocks[index]["text"])
                index += 1
            lines += [f"> {row}" for row in english_rows]
            lines.append("")
            lines += chinese_rows  # consecutive lines, so the renderer sees one table
            lines.append("")
            continue
        index += 1
        if kind == "heading":
            if not first_heading_seen and en["level"] == 1:
                first_heading_seen = True  # part title already printed
                continue
            hashes = "#" * min(6, max(2, en["level"] + level_shift))
            lines += [f"{hashes} {zh['text']}", f"*{en['text']}*", ""]
        elif kind == "subhead":
            lines += [f"**{zh['text']}**", f"*{en['text']}*", ""]
        elif kind == "stat":
            lines += [f"> {en['text']}", f"> **{zh['text']}**", ""]
        elif kind == "list":
            lines += [f"> - {en['text']}", f"- {zh['text']}", ""]
        else:
            lines += [f"> {en['text']}", "", zh["text"], ""]
        if kind == "caption" and figures:
            alternative = re.sub(r"\[\^\d+\]|[*`]", "", zh["text"]).strip()
            for entry in figures_for(figures, part["slug"], en["text"]):
                files = entry.get("files") or [entry.get("file")]
                lines += [f"![{alternative}]({image_prefix}{name})" for name in files if name]
                origin = entry.get("url_or_page") or entry.get("source") or ""
                note = entry.get("composition") or entry.get("note") or ""
                if origin:
                    lines += ["", f"<!-- 图源：{origin}。{note} -->", ""]
    if used:
        lines += ["---", "", f"{'#' * notes_heading_level} 本章脚注（沿用官方印刷版编号）", ""]
        for number in used:
            lines += [f"[^{number}]: {notes[str(number)]}", ""]
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    wanted = sys.argv[1:]
    notes = json.loads(REPORT.read_text(encoding="utf-8"))["footnotes"]
    figures = load_figures()
    if figures:
        print(f"figures: {len(figures)} entries in 对照稿/images/manifest.json")
    OUT_DIR.mkdir(exist_ok=True)
    failures = 0
    built = 0
    for part in PARTS:
        if wanted and part["slug"] not in wanted:
            continue
        en_path = ROOT / "sources" / "en" / f"{part['slug']}.en.md"
        zh_path = ROOT / "sources" / "zh" / f"{part['slug']}.zh.md"
        if not zh_path.exists():
            print(f"SKIP {part['slug']}: no translation yet")
            continue
        en_blocks = parse_blocks(en_path)
        zh_blocks = parse_blocks(zh_path)
        problems = validate(part["slug"], en_blocks, zh_blocks)
        if problems:
            failures += 1
            print(f"FAIL {part['slug']}:")
            for problem in problems:
                print("  -", problem)
            continue
        target = OUT_DIR / part["out"]
        target.write_text(render(part, en_blocks, zh_blocks, notes, figures=figures), encoding="utf-8")
        used = len({n for block in en_blocks for n in markers(block["text"])})
        built += 1
        print(f"OK   {part['slug']}: {len(en_blocks)} blocks aligned, {used} notes -> {target.relative_to(ROOT)}")
    print(f"\nbuilt {built} part(s), {failures} failure(s)")
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()