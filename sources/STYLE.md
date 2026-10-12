# 翻译体例（已确认）

本文件是《科学：一个新的黄金时代》中译的统一体例，供后续各章翻译与校对遵循。

## 版本形态

- **双语对照**：最终 EPUB 与对照稿都保留英文原文，英文在引用块（`>` / EPUB 中为次级样式）内，
  中文译文紧随其后；章节标题中英并列。
- **纯中文文本另存**：`sources/zh/*.zh.md` 只放译文，便于校对，也便于随时生成纯中文版本。
- **参考文献保留英文**：脚注（作者、题名、版本、URL）不译，以免改动可核查信息。

## 人名与专名

- **人名一律保留原文**，不音译：`Vannevar Bush`、`Donald Stokes`、`Shannon`、`Pasteur`、
  `Franklin D. Roosevelt`、`Trump`、`Michael Kratsios`、`Russ Vought`、`Donald J. Trump` 等。
  译文中的用法示例：「正如 Bush 所言」「第一届 Trump 政府」。
- **人名派生术语**保留原文并加通译提示：`Pasteur 象限`（通译「巴斯德象限」）。
- **作品名**用中文书名号 + 首次出现附原文：`《科学：无尽的前沿》（*Science: The Endless Frontier*）`。
- **机构与计划名**：缩写保留原文（NSF、DOE、NIH、NASA、NIST、DARPA、OMB、OSTP、STEM、
  ARPA、SBIR、STTR、CRADA、OTA、EUV、DOE 国家实验室、Genesis Mission、X-Labs）；
  首次出现可给中文全称，如「国家标准与技术研究院（NIST）」。有固定中文名的机构可用中文
  （国家科学基金会、能源部、国立卫生研究院）。
- **几处全书统一的定译**（改动前请先全书检索）：
  | 英文 | 定译 | 说明 |
  | --- | --- | --- |
  | `Department of War (DOW)` | 战争部（DOW，2025 年由国防部更名） | 首次出现给括注，其后作「战争部（DOW）」；不写「国防部」——那是 `Department of Defense` |
  | `use-inspired research` | 受使用意图启发的研究 | 全书统一（front、ch1、ch2、ch3、annex），不简作「受使用启发」 |
  | `intentional grantmaking` | 有意为之的资助 | 形容词性「intentional」按语境作「有意识的／刻意的」，名词短语统一作「有意为之的资助」 |
  | `Directorate`（NSF） | 学部 | 如 `Directorate for Technology, Innovation and Partnerships (TIP)` → 「技术、创新与伙伴关系学部（TIP）」，其后作「TIP 学部」 |
  | `program officer` | 项目官员 | 与「项目经理」（program manager）区分 |
  | `skilled technical workforce` | 技能型技术劳动力 | 全书统一 |
  | `Endnote numbering` | 官方印刷版编号 | `[^n]` 全书 1–185 连续 |
- **数字、单位、货币**：保留阿拉伯数字；英文缩写单位（$700 billion → 7,000 亿美元；
  $886B → 8,860 亿美元）换算为中文数量级。日期写「2026 年 7 月 21 日」。
- **倍数表述**：`risen N-fold` → 「增至原来的 N 倍」；`fallen N-fold` → 「降至原来的 N 分之一」
  （不写「下降了 N 倍」，汉语中易生歧义）；`increased by factors of X to Y` → 「增加了 X 到 Y 倍」；
  `doubled` → 「翻了一倍」，`more than triple` → 「三倍多」。

## 排版细节

- 汉字与拉丁字母/数字之间留一个空格（`tools/normalize_zh.py` 自动处理）。
- 引文用「」，书名用《》，括号用中文全角；英文原句中的引号在译文里换成「」。
- 脚注角标位置与原文一致；沿用**官方印刷版编号**（`[^n]`，全文 1–185 连续）。
- 破折号用「——」；不用半角 `--`。
- 图表只译图注，图内坐标轴与图例数字不译也不复制（数据以官方 PDF 原图为准）。
- 版面引文（pull quote，重复正文的放大句）不重复翻译。
- 术语一致性见 `样稿_第一章_引言_中英对照.md` 文末术语表；新增术语先补表再使用。

## 质量校验（每章必须通过）

```powershell
python tools/extract_source.py               # 重新抽取英文底本
python tools/verify_source.py chapter-0N     # 与官方 PDF 逐词比对，差异需能解释
python tools/verify_markers.py chapter-0N    # 脚注编号与印刷版一致
python tools/normalize_zh.py                 # 中拉空格规范化
python tools/build_sample.py chapter-0N      # 中英逐块对齐校验并出对照稿
```

`build_sample.py` 要求：段落数量、块类型序列、脚注编号序列三项完全一致，否则拒绝生成。

## 语义判断约定

- 直译会误导时按语义译，并在「译注」里说明（例：第一章 `basic laboratories` 指「简陋的实验室」，
  不是「基础实验室」）。
- 原文笔误（例：`suited to the answering the most important questions` 多一个 `the`）按语义处理，
  在译注中记录，不在正文中加「原文如此」。
- 原文本身含混或指涉不明的说法不替原文补足，照译其含糊（例：`The interest of vast scores of
  Americans ... has eroded`）。