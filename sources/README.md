# 正文来源与校对流水线

本目录保存《科学：一个新的黄金时代》的正文来源与逐段校对产物。旧的 EPUB 生成器
（`tools/build_chinese_epub.py`）直接从 PDF 文本层取段落，会把页码、页眉、脚注编号和
断行连字符一起带进正文，导致句子在中途被切断、脚注数字散落在译文里。新流水线改用
官方网页版正文，并对每个环节留证。

## 文件

| 路径 | 内容 |
| --- | --- |
| `whitehouse-science.html` | 官方网页版缓存（`tools/fetch_source.py` 下载） |
| `report.json` | 结构化正文：67 个小节、段落/列表/图注/数据块、185 条脚注 |
| `en/*.en.md` | 分章英文正文，作为翻译底本 |
| `zh/*.zh.md` | 人工译文，与英文逐块一一对应 |

## 流水线

```powershell
python tools/fetch_source.py        # 1. 下载官方网页版并缓存
python tools/extract_source.py      # 2. 抽取结构化正文 + 分章 Markdown
python tools/verify_source.py chapter-01   # 3. 与官方 PDF 逐词比对（差异清单）
python tools/verify_markers.py chapter-01  # 4. 脚注编号与 PDF 印刷版逐一核对
python tools/build_sample.py        # 5. 组装并校验中英对照稿
```

`tools/build_sample.py` 在生成前强制校验英文与中文稿的段落数量、块类型与脚注编号序列，
不一致即报错退出，因此不会出现"译文少一段"或"脚注错位"的情况。

## 已知的源文件问题

- **脚注编号**：网页版正文中的角标数字整体比印刷版大 1，且注释表漏排了印刷版的第 13 条
  （National Center for Science and Engineering Statistics, *National Patterns of R&D
  Resources: 2023-24 Data Update*）。`tools/extract_source.py` 以网页版列表项的锚点
  `id - 1` 还原印刷版编号，`tools/align_note_lists.py` 的输出即为对齐证据；全篇 185 条、
  编号 1–185 连续无缺。`tools/verify_markers.py` 再逐条把网页版角标与其后文拿去对照印刷版
  PDF 的文字层：190 条（报告 185 + 备忘录 5）中 184 条直接命中（第一章 25/25、第三章 38/38、
  第四章 23/23、第五章 39/42、第二章 54/57、附录 5/5）。剩下 6 条（[^26] [^39] [^56]
  [^144] [^145] [^168]）是文字层抽取问题：角标紧跟斜体引文，探针里带 Markdown 的 `*`，
  PDF 里自然找不到该字符串，并非编号错位；逐条记录见 `tools/_marker_check_chapter-02.txt`
  与 `tools/_marker_check_chapter-05.txt`。
- **原文笔误**：第一章 I.4 节结尾 "suited to the answering the most important questions"
  多一个 `the`；两版一致，译文按语义处理。
- **原文笔误（其余各章，均按语义处理，未在正文加「原文如此」）**：
  | 位置 | 原文 | 应为 |
  | --- | --- | --- |
  | 第二章 Figure 4 图注 | `early forties today**,** across all degree types` | 多余的粗体标记 |
  | 第二章 II.13 | `read the unopenable Herculaneum scrolls` | `read the unopenable ...`（缺 `the`） |
  | 第二章 II.14 | `The list of examples go on` | `goes on` |
  | 第二章 II.15 | `A DOW unit might experiment ...` | 与 NIH/NSF 并列讲资助裁量，英文作 `DOW`；第四章 `DOW's eight Microelectronic Commons regional hubs` 与第三章 `tested by the DOE or DOW` 表明 `DOW` 是有意使用的现行部名，故一律照原文作 `DOW` |
  | 第三章 | `As the time of writing` | `At the time of writing` |
  | 第三章 | `live-saving therapies` | `life-saving` |
  | 第三章 | `in our part of the century` | 表述不地道，疑为 `in this part of the century` |
  | 第五章 | `America's premier –"AI for science" initiative` | 多余的破折号 |
  | 附录 | `Achieving these objectives require Federal investments` | `requires` |
  | 附录 | `the National Institute of Health (NIH)` | 官方名为 `National Institutes of Health` |
- **附录文本差异**：2028 财年备忘录在报告附录中重印时，「Increase Grant Durations」一条写作
  "Agencies should develop proposals for the FY 2028 Budget that would expand the number of
  long-duration grants"，而单独发布的备忘录写作 "Agencies should expand the number of
  long-duration grants"。本项目采用单独发布版的措辞，并在此登记差异。
- **版面引文（pull quote）**：官方网页与 PDF 会用大字重复正文句子，抽取时按注释跳过，
  避免同一句在电子书中出现两次。
- **图表**：PDF 图表内的坐标轴数字与图例不再进入正文，只保留图注；原图另存于
  `对照稿/images/`（由 `tools/extract_figures.py` 从 PDF 的矢量图渲染，报告内所有图表都是
  矢量绘制，页面里没有图表位图）。核对时发现的几处「图注与图形不完全一致」：
  图 2 图注只提美国与中国，图上还画了 EU 27；图 3 图注写「约 20% 升至 40%」，曲线峰值约 48%；
  图 4 图内标题把 EQUIVALENT 拼成 `EQUIVELENT`（原图印刷错误，译文与 manifest 均照实记录）。
  报告只有图 1–图 4，第三至五章与 2028 财年备忘录都没有图表；第二章表 1 是真正的 HTML 表格，
  不是图片。
- **两版差异（前言）**：印刷版致总统函带有抬头/收件人区块（The Honorable Donald J. Trump,
  The White House, Washington, D.C.）与 `/s/ MICHAEL J. KRATSIOS, Director` 签名行，
  网页版省略了收件人区块、并把签署人职务写全（Assistant to the President for Science and
  Technology / Director, Office of Science and Technology Policy）。译文按网页版正文翻译，
  前述抬头与签名形式差异已在此登记，需要时可在排版阶段按印刷版补回。
- **附录来源**：网页版只给出 FY2028 备忘录的链接，正文取自单独的备忘录 PDF
  （`sources/White-House-Fiscal-Year-2028-RD-Priorities-Memorandum.pdf`），由
  `tools/extract_annex.py` 抽取；`tools/extract_source.py` 通过 `EXTERNAL_SOURCES`
  白名单避免覆盖该文件。
- **印刷版目录**：PDF 物理页 3–4 的目录属于导航，不属于报告正文，因此前言比对范围取
  物理页 5–18（相似度 93.9%，差异为目录尾部、页眉与抬头区块）。