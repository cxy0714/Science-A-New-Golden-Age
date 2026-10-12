#!/usr/bin/env python3
"""Assemble the whole bilingual book into one Markdown file.

Reuses the per-part validation in tools/build_bilingual.py: a part is only included
after its block sequence, section numbers and endnote markers have been proven to
match the English source. Figures are embedded from 对照稿/images/manifest.json.

Usage: python tools/build_book_md.py
"""

from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_bilingual import (  # noqa: E402
    OUT_DIR,
    PARTS,
    REPORT,
    figures_for,
    load_figures,
    markers,
    parse_blocks,
    render,
    validate,
)

BOOK = ROOT / "科学_一个新的黄金时代_中英对照.md"
IMAGE_PREFIX = "对照稿/images/"

FRONT = """# 科学：一个新的黄金时代 · *Science: A New Golden Age*

> 中英对照全本 · 白宫科学技术政策办公室（OSTP）2026 年 7 月 21 日提交总统的报告
>
> **怎么读**：每一段先给英文原文（引用块），紧接中文译文；章节标题与图表标题中英并列。
> 人名保留原文（Vannevar Bush、Donald Stokes、Trump 等），机构缩写保留原文并在首次出现时给中文全称。
> `[^n]` 沿用**官方印刷版**脚注编号（全书 1–185 连续），注释按章附在每章末尾，参考文献保留英文。
> 图 1–图 4 取自官方发布的原始图表，正文中按图注位置插在对应段落之后。

## 目录

"""


def main() -> None:
    notes = json.loads(REPORT.read_text(encoding="utf-8"))["footnotes"]
    figures = load_figures()
    included: list[tuple[dict, list[dict], list[dict]]] = []
    skipped: list[str] = []
    failed: list[str] = []

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
            failed.append(f"{part['slug']}: {problems[0]}")
            continue
        included.append((part, en_blocks, zh_blocks))

    lines = [FRONT.rstrip(), ""]
    for index, (part, en_blocks, _) in enumerate(included, start=1):
        used = len({n for block in en_blocks for n in markers(block["text"])})
        label = f"{index}. {part['zh']}"
        lines.append(f"{label}（{len(en_blocks)} 段{'，' + str(used) + ' 条脚注' if used else ''}）")
    lines.append("")

    for part, en_blocks, zh_blocks in included:
        body = render(
            part,
            en_blocks,
            zh_blocks,
            notes,
            figures=figures,
            image_prefix=IMAGE_PREFIX,
            level_shift=0,
            title_level=1,
            notes_heading_level=2,
        )
        # Drop the per-part provenance header: the book states it once, up front.
        body = body.split("\n", 2)[2] if body.startswith("> 中英对照稿") else body.split("\n\n", 1)[1]
        lines += [body.rstrip(), "", "---", ""]

    BOOK.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    words_en = sum(len(b["text"].split()) for _, blocks, _ in included for b in blocks)
    words_zh = sum(len(b["text"]) for _, _, blocks in included for b in blocks)
    print(f"wrote {BOOK.relative_to(ROOT)}")
    print(f"parts included: {len(included)}  english words ≈ {words_en}  chinese chars ≈ {words_zh}")
    if figures:
        print(f"figures available: {len(figures)}")
    for part, en_blocks, _ in included:
        embedded = [e["file"] for b in en_blocks if b["type"] == "caption" for e in figures_for(figures, part["slug"], b["text"])]
        print(f"  {part['slug']:14s} {len(en_blocks):3d} blocks  images: {', '.join(embedded) if embedded else '—'}")
    if skipped:
        print("MISSING translation:", ", ".join(skipped))
    if failed:
        print("ALIGNMENT FAILURES:")
        for item in failed:
            print("  -", item)
        sys.exit(1)


if __name__ == "__main__":
    main()