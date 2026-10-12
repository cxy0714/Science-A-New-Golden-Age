# 《科学：一个新的黄金时代》中英双语版

白宫报告 *Science: A New Golden Age: A Report to the President*（OSTP，2026 年 7 月 21 日）的**中英对照**电子书与 Markdown 文本。中文为人工重译（非官方译本），英文取自官方网页版并与官方 PDF 逐词核对。

## 下载

| 文件 | 说明 |
| --- | --- |
| [科学_一个新的黄金时代_中英对照.epub](./科学_一个新的黄金时代_中英对照.epub) | **推荐**：双语对照，每段先英文原文（淡色引用块），后中文译文；脚注可点击跳转；含图 1–图 4 |
| [科学_一个新的黄金时代_中文.epub](./科学_一个新的黄金时代_中文.epub) | 纯中文版（同一译文，去掉英文对照），适合通读 |
| [科学_一个新的黄金时代_中英对照.md](./科学_一个新的黄金时代_中英对照.md) | 全书合并的中英对照 Markdown（图片在 `对照稿/images/`） |
| [对照稿/](./对照稿) | 分篇对照稿（前言、第一至五章、2028 财年备忘录）与图表文件 |

适用于 Apple Books、Calibre、Kobo、PocketBook 等支持 EPUB 3 的阅读器。

## 书中内容

- 前言：致总统函、Trump 总统的来信、报告摘要
- 第一章 引言 · 第二章 振兴美国科学技术事业 · 第三章 确保美国在关键与新兴技术上的主导地位
- 第四章 让科学技术改善所有美国人的生活 · 第五章 一个新的黄金时代
- 附录：2028 财年政府研发预算优先事项备忘录（NSTM-5 / M-26-16）
- 图 1–图 4 与数据卡片（如「每 3 个美国人中就有 1 人所在县没有任何研发雇主」）
- 脚注 1–185，按章列于章末，编号与官方印刷版一致

## 体例

- **人名保留原文**：`Vannevar Bush`、`Donald Stokes`、`Shannon`、`Pasteur`、`Trump` 等不音译；人名派生术语保留原文并加通译提示（如 `Pasteur 象限`）。
- **机构缩写保留原文**（NSF、NIH、DOE、DARPA、OMB、OSTP 等），首次出现给中文全称。
- **参考文献保留英文**，不改动作者、题名、版本与 URL。
- 脚注编号沿用**官方印刷版**：网页版正文的角标数字整体偏移 +1，且注释表漏排了印刷版第 13 条；本项目以网页列表锚点还原为印刷版编号（全书 1–185 连续）。详见 [`sources/README.md`](./sources/README.md)。
- 中文引文用「」，书名用《》；中拉之间留一个空格（`tools/normalize_zh.py` 统一处理）。
- 完整体例见 [`sources/STYLE.md`](./sources/STYLE.md)。

## 原文与引用说明

- 官方网页：[whitehouse.gov/science](https://www.whitehouse.gov/science/)
- 官方 PDF：[Science-A-New-Golden-Age.pdf](https://www.whitehouse.gov/wp-content/uploads/2026/07/Science-A-New-Golden-Age.pdf)

这是非官方译本，供阅读参考。政策措辞、数字、专有名词、脚注与引文请以官方英文原文（及官方 PDF）为准；引用报告时应引用原文，而不是本电子书。

## 流水线

```powershell
python tools/fetch_source.py             # 抓取官方网页版正文（缓存到 sources/）
python tools/extract_source.py           # 抽取英文底本 -> sources/en/*.en.md + sources/report.json
python tools/extract_annex.py            # 2028 财年备忘录单独取自其官方 PDF -> sources/en/annex-fy2028.en.md
python tools/verify_source.py chapter-01 # 与官方 PDF 逐词比对（相似度与差异簇）
python tools/verify_markers.py chapter-01# 脚注编号与印刷版逐一核对
python tools/extract_figures.py           # 从官方 PDF 矢量图渲染 图 1–图 4 -> 对照稿/images/ + manifest.json
python tools/normalize_zh.py             # 中拉空格规范化
python tools/lint_zh.py                  # 译文体检：页码残留、半角标点、表格单元格、未译句
python tools/build_bilingual.py          # 逐块强制对齐校验 + 生成 对照稿/*.md
python tools/build_book_md.py            # 合并为全书 Markdown
python tools/build_bilingual_epub.py     # 生成中英对照 EPUB 与纯中文 EPUB
python tools/check_epub.py               # 校验 EPUB：XML、内链、图片、页码残留、中英配对
python tools/verify_all.py               # 一次跑完全部校验（--fast 跳过 PDF 比对）
```

`build_bilingual.py` 会在段落数量、块类型序列、章节编号、脚注编号四项中任何一项不一致时**拒绝生成**，因此翻译文件必须与英文文件逐块对应。长章节可用 `tools/check_part.py` 分片翻译、`tools/assemble_fragments.py` 合并（第二章即由四段译文合并，再分两半复核）。

## 校订情况

全书经过两轮：先逐块翻译，再由独立的校对代理逐章对照英文复核，只改真错（漏译、加译、数字与专名错误、术语不一致、翻译腔），改完必须重跑对齐校验。累计修正如「城市规模的芯片交响乐团协同工作 → 城市规模的芯片如同交响乐团般协同运作」「最优秀的大脑 → 最优秀的人才」「把一个反应堆设计的这一流程 → 仅这一种反应堆设计的审批流程」等 190 余处；`Department of War (DOW)`、`use-inspired`、`intentional grantmaking`、NSF 的 `Directorate` 等定译见 [`sources/STYLE.md`](./sources/STYLE.md)。

## 目录结构

```
sources/en/          英文底本（按篇章拆分，取自官方网页版；附录取自备忘录 PDF）
sources/zh/          中文译文（与英文逐块对应）；attic/ 存放分片翻译过程稿
sources/report.json  正文结构 + 185 条脚注文本
sources/figures-web/ 官方网页版图表 PNG 原件（作为备选与比对依据）
对照稿/              分篇中英对照 Markdown + images/（图 1–图 4 原图与 manifest.json）
tools/               抓取、抽取、核对、排版、生成与校验脚本；_*.txt 为各次核对的原始记录
```

## 旧版说明

[科学_一个新的黄金时代_中文机器初译.epub](./科学_一个新的黄金时代_中文机器初译.epub) 是早期流水线的产物，已被上面两个版本取代。它的缺陷有据可查：用 `pdftotext -raw` 逐视觉行抓取 PDF，页码（如 29/30/31）、页眉（如 `Chapter II – Introduction`）、脚注角标与断词连字符留在正文里，再按空行分段交给机器翻译，导致整页甚至整章被当成一个段落、句子在任意位置被切断。诊断与逐项核对记录见 [`sources/README.md`](./sources/README.md)，第一章试译样稿见 [样稿_第一章_引言_中英对照.md](./样稿_第一章_引言_中英对照.md)。