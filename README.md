# 《科学：一个新的黄金时代》中文 EPUB

本仓库提供白宫报告 *Science: A New Golden Age: A Report to the President* 的中文 EPUB 机器初译。

## 下载

[下载 EPUB 电子书](./科学_一个新的黄金时代_中文机器初译.epub)

适用于 Apple Books、Calibre、Kobo、PocketBook 和大多数支持 EPUB 3 的阅读器。

## 书中内容

- 扉页与机器初译说明
- 致总统函、总统致函与报告摘要
- 第一章：引言
- 第二章：振兴美国科技企业
- 第三章：确保美国主导关键与新兴技术
- 第四章：让科技改善所有美国人的生活
- 第五章：一个新的黄金时代
- FY2028 研发优先事项备忘录
- 官方英文参考资料与链接

电子书包含目录和章节导航。正文及 FY2028 备忘录为中文机器初译；参考文献保留英文原文，以免改动作者、题名、版本信息或 URL。

## 原文与使用说明

- 官方网页：[The White House - Science: A New Golden Age](https://www.whitehouse.gov/science/)
- 官方 PDF：[Science-A-New-Golden-Age.pdf](https://www.whitehouse.gov/wp-content/uploads/2026/07/Science-A-New-Golden-Age.pdf)
- 报告发布于 2026 年 7 月，作者为 Michael Kratsios，白宫科学技术政策办公室主任。

这是非官方机器译本。政策措辞、数字、专有名词、脚注和引文请以官方英文 PDF 为准；引用报告时应引用原文，而不是本电子书。

## 重新生成

生成器在 [`tools/build_chinese_epub.py`](./tools/build_chinese_epub.py)。将官方 PDF 下载到仓库根目录后，在安装了 Python 3 与 Poppler/Xpdf `pdftotext` 的环境运行：

```powershell
python tools/build_chinese_epub.py
```

脚本会生成 EPUB，并在运行时缓存机器翻译结果；缓存不会被提交到仓库。
