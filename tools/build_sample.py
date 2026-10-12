#!/usr/bin/env python3
"""Assemble and validate the bilingual Chapter I sample for review.

Pairs the English source (sources/en/<slug>.en.md, extracted from the official web
edition and cross-checked against the printed PDF) with the Chinese translation
(sources/zh/<slug>.zh.md) block by block, refusing to build if the two files are
not perfectly aligned.

Usage: python tools/build_sample.py [slug]        (default: chapter-01)
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
REPORT = ROOT / "sources" / "report.json"

PARTS = {
    "chapter-01": {
        "en": "Chapter I: Introduction",
        "zh": "第一章 引言",
        "out": "样稿_第一章_引言_中英对照.md",
        "title": "第一章 引言（试译样稿）",
    }
}

INTRO = """# 第一章 引言（试译样稿）

> **这份样稿是什么。** 这是《科学：一个新的黄金时代》（*Science: A New Golden Age*）第一章的中英对照试译，供您判断译文风格与体例。英文原文取自白宫官方网页版（与官方 PDF 正文逐段核对，见下），中文为本次重译，不是机器直译。
>
> **为什么要重做。** 此前 EPUB 的问题不是「某个词译错」，而是**翻译单位被切坏了**：旧流程用 `pdftotext -raw` 抓 PDF，保留了每一视觉行；页码、页眉、脚注编号、连字符断词全都留在正文里，然后按空行分段——于是一整页甚至一整章被当成一个段落交给机器翻译，句子在任意位置被切断，译文只好逐行猜意思。您看到的 **29、30、31** 就是这么来的，共三处：
>
> 1. **目录页码**。旧 EPUB 的前言部分把整页目录塞进了一个段落：`……未来想法 29 / 采用投资组合的方法 30 / 推动不断创新 31 / 目录`。
> 2. **脚注编号**。第二章正文里脚注数字被当成了句尾内容：`……者提高到 30`、`……然后急剧下降到 31`。
> 3. **页码与页眉**。每页的 `29`、`30`、`31` 以及 `Chapter II – Introduction` 这类页眉，被当作正文混进段落中间。
>
> 更严重的是版面切断造成的错译，例如旧译文把 “Against the backdrop of pre-War federal research funding...” 译成「**反对**战前联邦研究经费……」——因为 `Against` 正好落在行首，模型只看到半句。另外旧 EPUB 的第一章开头缺了整整一页：`第一章——引言` 之后直接从「90% 的病例普遍致命且无法治愈」开始，因为分章边界切错了位置。
>
> **这一稿怎么做的。** 正文改用官方**网页版**（与 PDF 同一文本，但段落完整、无页码页眉、无断词连字符），并做四项自动校验：① 与官方 PDF 逐词比对（第一章相似度 95.3%，差异仅为图表内部数字与页码）；② 25 处脚注编号逐一与 PDF 印刷版核对，全部一致；③ 中英段落一一对应（本脚本强制校验，不通过则不生成样稿）；④ 原 PDF 中的图表坐标轴数字不再进入正文，改为图注 + 说明。纯中文（无英文对照）的本章文本在 `sources/zh/chapter-01.zh.md`。
>
> **体例。** 英文原文用引用块（`>`）给出，中文译文紧随其后；`[^n]` 沿用官方印刷版脚注编号（1–25）；正文中的 *图 1/2/3* 为原文图表，图注照译，图内数据未复制。参考文献（脚注）保留英文，以免改动作者、题名、版本与 URL。
>
> **请重点看这几件事**：政策术语的译法（见文末术语表）、长句的断句与语序，“enterprise / legacy institutions / translation / craft” 这类多义词的取舍、以及脚注位置是否与原文一致。
"""

GLOSSARY = """## 术语对照表

| 英文 | 本稿译法 | 说明 |
| --- | --- | --- |
| the scientific enterprise | 科学事业 / 科研体系 | 指整个科研活动的组织总体，不是单个"企业"；企业界另译"产业界、企业" |
| legacy institutions | 既有机构 / 传统机构 | 指大学、联邦机构等历史形成的机构，含"路径依赖"意味 |
| scientific machine | 科学这部机器 | 保留原文比喻；亦可意译为"科研运行机制" |
| the frontier | 前沿 | "frontier"同时呼应布什《无尽的前沿》，故不译"边界" |
| basic research | 基础研究 | 与 applied research（应用研究）对举 |
| use-inspired research | 受使用意图启发的研究 | 斯托克斯"巴斯德象限"概念，指同时追求根本理解与用途 |
| Pasteur's quadrant | 巴斯德象限 | 保留学界通用译名 |
| linear model | 线性模型 | 指基础研究→应用研究→开发的单向链条 |
| principal investigator (PI) | 首席研究员（PI） | 保留缩写便于对照原文 |
| indirect cost rate / overhead | 间接成本率 / 间接费用 | 指大学从项目经费中提取的管理费比例 |
| translation（of research） | 转化 | 指发现变为产品、能力、产业；不译"翻译" |
| craft | 技艺 | 与 science 对举，含工艺、手艺、技能等默会知识 |
| tacit knowledge | 默会知识 | 与显性知识（explicit knowledge）对举 |
| research security | 科研安全 | 政策术语，指防范研究被外国利用 |
| metascience | 元科学 | 研究"科学如何做"的科学 |
| portfolio-based approach | 组合管理方式 | 把资助组合当作投资组合来评估 |
| purchasing power parity (PPP) | 购买力平价 | 保留缩写 PPP |
| land-grant universities | 赠地大学 | 1862 年《莫里尔法案》体系下的州立大学 |
| STEM pipeline | STEM 人才通道 | 保留 STEM 缩写；pipeline 指从求学到的培养链条 |
| Extreme Ultraviolet (EUV) lithography | 极紫外（EUV）光刻 | 光刻机关键工艺 |
| National Science Foundation (NSF) | 国家科学基金会 | 正文保留原缩写，便于与原文对照 |
| Department of Energy (DOE) | 能源部 | 同上 |
| National Institutes of Health (NIH) | 国立卫生研究院 | 同上 |
| Vannevar Bush | 万尼瓦尔·布什 | 通用译名；旧稿中的"范内瓦·布什"为非通用写法 |
| Science: The Endless Frontier | 《科学：无尽的前沿》 | 1945 年报告，中译本沿用此名 |
| As We May Think | 《诚如所思》 | 布什 1945 年论文，本报告第五章引用 |

## 译注（原文疑点与处理）

1. **原文第 I.3 节 "a dozen engineers in basic laboratories"**：此处 `basic` 意为"简陋的、基础的（设施）"，不是"基础研究"。旧译文按"基础实验室"直译会误导，本稿译作"简陋的实验室"。
2. **原文第 I.4 节 "suited to the answering the most important questions"**：官方 PDF 与网页版都有多余的 `the`，属原文笔误；本稿按语义译出，未加注说明于正文。
3. **原文第 I.9 节 "The interest of vast scores of Americans ... has, consequently, eroded."**：语义为"广大美国人的兴趣已被侵蚀"，本稿按此译出；该句本身指涉不明（"兴趣"具体指何种民意），不宜替原文补足。
4. **pull quote（版面引文）不重复翻译**：官方网页与 PDF 在章内多处用大字重复正文句子（如 I.3、I.6、I.9 各一处）。这些重复句不进入译文，避免同一句在电子书里出现两次。
5. **图表**：官方 PDF 的图 1–3 带有坐标轴数字与图例（如 `1957 1963 … 2023`、`1,200 1,000 …`）。旧 EPUB 把这些数字当成正文译了进去；本稿只保留图注，数据请查官方 PDF 原图。
"""


def parse_blocks(path: pathlib.Path) -> list[dict]:
    blocks: list[dict] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("<!--"):
            continue
        if line.startswith("#"):
            blocks.append({"type": "heading", "text": line.lstrip("# ").strip()})
        elif line.startswith(">"):
            blocks.append({"type": "stat", "text": line.lstrip("> ").strip()})
        elif re.fullmatch(r"\*[^*].*\*", line):
            blocks.append({"type": "caption", "text": line.strip("*")})
        elif line.startswith("- "):
            blocks.append({"type": "list", "text": line[2:].strip()})
        else:
            blocks.append({"type": "paragraph", "text": line})
    return blocks


def markers(text: str) -> list[str]:
    return re.findall(r"\[\^(\d+)\]", text)


def clean_inline(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def main() -> None:
    slug = sys.argv[1] if len(sys.argv) > 1 else "chapter-01"
    part = PARTS[slug]
    en_path = ROOT / "sources" / "en" / f"{slug}.en.md"
    zh_path = ROOT / "sources" / "zh" / f"{slug}.zh.md"
    en_blocks = parse_blocks(en_path)
    zh_blocks = parse_blocks(zh_path)

    problems: list[str] = []
    if len(en_blocks) != len(zh_blocks):
        problems.append(f"block count differs: en={len(en_blocks)} zh={len(zh_blocks)}")
    for index, (en, zh) in enumerate(zip(en_blocks, zh_blocks)):
        label = f"block {index + 1} ({en['type']})"
        if en["type"] != zh["type"]:
            problems.append(f"{label}: type mismatch (en={en['type']}, zh={zh['type']})")
            continue
        if en["type"] == "heading":
            # Only numbered section headings ("I.1 ...") carry a number to compare;
            # the part title is translated freely.
            if re.match(r"^[IVX]+\.\d+", en["text"]) or re.match(r"^[IVX]+\.\d+", zh["text"]):
                if en["text"].split(" ", 1)[0] != zh["text"].split(" ", 1)[0]:
                    problems.append(f"{label}: section number mismatch ({en['text'][:30]} / {zh['text'][:30]})")
            continue
        if markers(en["text"]) != markers(zh["text"]):
            problems.append(f"{label}: note markers differ\n    en={markers(en['text'])}\n    zh={markers(zh['text'])}")
    if problems:
        print("ALIGNMENT FAILED — sample not written:")
        for problem in problems:
            print(" -", problem)
        sys.exit(1)

    notes = json.loads(REPORT.read_text(encoding="utf-8"))["footnotes"]
    used = sorted({int(n) for block in en_blocks for n in markers(block["text"])})

    lines = [INTRO, "---", ""]
    lines.append(f"## {part['title'].split('（')[0]} · *{part['en']}*")
    lines.append("")
    index = 0
    while index < len(en_blocks):
        en, zh = en_blocks[index], zh_blocks[index]
        if en["type"] == "heading" and not re.match(r"^[IVX]+\.\d+", en["text"]):
            index += 1  # part title is already printed above
            continue
        if en["type"] == "heading":
            number, _, en_title = en["text"].partition(" ")
            _, _, zh_title = zh["text"].partition(" ")
            lines += [f"### {number} {zh_title}", f"*{en_title}*", ""]
        elif en["type"] == "stat":
            lines += [f"> {clean_inline(en['text'])}", f"> **{clean_inline(zh['text'])}**", ""]
        else:
            lines += [f"> {clean_inline(en['text'])}", "", clean_inline(zh["text"]), ""]
        index += 1

    lines += ["---", "", "## 本章脚注（沿用官方印刷版编号）", ""]
    for number in used:
        lines += [f"[^{number}]: {notes[str(number)]}", ""]

    lines += ["---", "", GLOSSARY.rstrip(), ""]
    lines += ["---", "", "## 下一步", "",
              "1. 您确认风格与术语后，我按同一流程处理前言、第二至五章、FY2028 备忘录与参考文献，逐章交付中英对照稿。",
              "2. 全部定稿后重写 EPUB 生成器：按段落对（原文/译文）排版，脚注以超链接形式落到章末或书末注释，图表用官方 PDF 的图注，不再把 PDF 页码与页眉带进正文。",
              "3. 交付物：修订版中文 EPUB（含目录、章节导航、脚注链接）＋ 全书中英对照 Markdown。", ""]

    out = ROOT / part["out"]
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"OK: {len(en_blocks)} blocks aligned, {len(used)} notes used -> {out.name}")


if __name__ == "__main__":
    main()