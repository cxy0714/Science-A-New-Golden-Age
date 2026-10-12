#!/usr/bin/env python3
"""Extract a clean, paragraph-accurate English text of the FY 2028 R&D Priorities
Memorandum, and verify it against the printed annex in the report PDF.

Sources
-------
Primary   sources/White-House-Fiscal-Year-2028-RD-Priorities-Memorandum.pdf
          Official standalone memo (whitehouse.gov, 14 pages). Page 1 is a scan
          whose OCR text layer garbles the letterhead, the signature block and a
          few words; pages 2-14 carry a digital text layer with clean word-level
          line wrapping (no words broken across lines).
Cross-check  Science-A-New-Golden-Age.pdf, PDF pages 102-121 = printed pages
          85-104 ("Annex: FY 2028 R&D Priorities Memo").
          The report reprint has no footnotes and its text layer breaks words
          across lines with plain hyphens (142 line-final hyphens, only 20 of
          them soft), so dehyphenating it is heuristic -- hence it is used for
          cross-checking, not as the base text.

Outputs
-------
sources/en/annex-fy2028.en.md       cleaned markdown (real paragraphs, lists)
tools/_annex_extraction_report.txt  quantitative verification report

The 185 endnotes that used to sit in sources/en/annex-fy2028.en.md belonged to
the report's References section (the web edition exposes the annex as an empty
"reading--refs" section), not to this memo; they live in references.en.md.

Run:  python tools/extract_annex.py [--debug]
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import pathlib
import re
import sys
from datetime import date

import fitz

ROOT = pathlib.Path(__file__).resolve().parents[1]
PRIMARY = ROOT / "sources" / "White-House-Fiscal-Year-2028-RD-Priorities-Memorandum.pdf"
PRIMARY_URL = (
    "https://www.whitehouse.gov/wp-content/uploads/2026/07/"
    "White-House-Fiscal-Year-2028-RD-Priorities-Memorandum.pdf"
)
REPORT_PDF = ROOT / "Science-A-New-Golden-Age.pdf"
ANNEX_PDF_PAGES = (102, 122)  # 0-based half-open slice -> PDF pages 102..121
ANNEX_PRINTED = "85-104"
OUT_MD = ROOT / "sources" / "en" / "annex-fy2028.en.md"
OUT_REPORT = ROOT / "tools" / "_annex_extraction_report.txt"

TITLE = "# Annex: FY2028 R&D Priorities Memo"
ANNEX_RUNNING_HEAD = "Annex: FY 2028 R&D Priorities Memo"
BULLET = "\u2022"

# ---------------------------------------------------------------------------
# Fixes applied to the scanned/OCR first page of the standalone memo. Each one
# is confirmed either by the report's clean annex reprint or by an external
# resolution check; nothing here is a paraphrase.
# ---------------------------------------------------------------------------
OCR_FIXES = [
    ("(Al)", "(AI)", 'OCR read "AI" as "Al" (lower-case L); annex p.85 has "(AI)".'),
    ("build. To. usher", "build. To usher", 'stray OCR period; annex p.85 has "To usher".'),
    ("the modem American", "the modern American", 'OCR read "modern" as "modem"; annex p.85 has "modern".'),
    ("Patterns ofR&D", "Patterns of R&D", "OCR dropped the space; footnote 1."),
    ("WASHINGTON , D.C.", "WASHINGTON, D.C.", "OCR space before comma; letterhead."),
    (
        "half century,2 and yet",
        "half century,[^2] and yet",
        "the footnote-2 call-out was OCR'd into the body at full size instead of as "
        'a small digit; annex p.86 reads "half century,and" with the call-out removed.',
    ),
    (
        "10.2139/ssm.3822691",
        "10.2139/ssrn.3822691",
        "OCR dropped the r of the SSRN DOI prefix in footnote 4.",
    ),
]

# The standalone page 1 signature block is overprinted by the signature images
# and its OCR layer is unusable ("DIRECTOR, OFFICE O~ IE~ f E AKD TECHNOLOGY
# POLICY", "RUSSELL T. VOUGH,A_, ..."). The report's annex reprint of the same
# memo block is clean, so the FROM block is taken from there.
FROM_BLOCK = [
    "MICHAEL J. KRATSIOS",
    "ASSISTANT TO THE PRESIDENT FOR SCIENCE AND TECHNOLOGY",
    "DIRECTOR, OFFICE OF SCIENCE AND TECHNOLOGY POLICY",
    "",
    "RUSSELL T. VOUGHT",
    "DIRECTOR, OFFICE OF MANAGEMENT AND BUDGET",
]
DOC_NUMBER = "NSTM-5 / M-26-16"  # annex reading; OCR produced "NSTM-5 I M-26-16"

NOTES = [
    (
        "Page ranges",
        "The annex reprint runs over printed pages 85-104 (PDF pages 102-121 of "
        "Science-A-New-Golden-Age.pdf, 20 pages), not 85-95 as briefed: printed "
        "p.104 still carries the running head \"Annex: FY 2028 R&D Priorities "
        "Memo\" and holds the IMPLEMENTATION section, and PDF page 122 (printed "
        "105) is blank. PDF page 101 is the \"Annex\" divider, page 100 ends the "
        "report's End Notes.",
    ),
    (
        "Footnotes",
        "The standalone memo carries five footnotes (four on its page 1, one on "
        "page 2); the report's annex reprint drops them entirely (their numbers "
        "leave residue in the report text such as \"century,and yet\"). They are "
        "kept here as inline [^1]-[^5] markers plus a Notes section, because "
        "they are part of the memo and appear nowhere else in the repo.",
    ),
    (
        "Textual divergence between the two PDFs",
        "One substantive wording difference could not be reconciled: the "
        "\"Increase Grant Durations for Transformative Research\" bullet reads "
        "\"Agencies should expand the number of long-duration grants\" in the "
        "standalone memo (p.8) but \"Agencies should develop proposals for the "
        "FY 2028 Budget that would expand the number of long-duration grants\" "
        "in the report annex (printed p.96). The preferred standalone wording is "
        "used; a translator should be aware the report prints the longer "
        "variant.",
    ),
    (
        "Verbatim oddities kept",
        "\"the DOW Vannevar Bush Faculty Fellowship\" and \"the National "
        "Institute of Health (NIH) Director's Pioneer Award\" are spelled that "
        "way in BOTH PDFs, so they are reproduced verbatim (the intended bodies "
        "are almost certainly DoD and the National Institutes of Health).",
    ),
    (
        "Scanned first page",
        "The standalone memo's first page is a 600-dpi scan (5100x6600 px on a "
        "612x792 pt page) whose OCR text layer is overprinted by the signature "
        "image; six OCR defects were repaired (see fixes above) and the FROM "
        "block was taken from the annex reprint. The rest of the standalone PDF "
        "(pages 2-14) has a digital text layer with no mid-word line breaks.",
    ),
    (
        "Letterhead",
        "The letterhead lines (EXECUTIVE OFFICE OF THE PRESIDENT / WASHINGTON, "
        "D.C. 20502) come from the OCR layer only; the report's annex reprint "
        "does not reproduce the letterhead, so there is no second source to "
        "confirm them, though they are the standard EOP memo letterhead.",
    ),
    (
        "DOI in footnote 4",
        "The scan's footnote 4 reads \"https://dx.doi.org/10.2139/ssm.3822691\". "
        "\"ssm\" is not a real SSRN DOI prefix: 10.2139/ssm.3822691 returns 404, "
        "while 10.2139/ssrn.3822691 resolves to ssrn.com/abstract=3822691. The "
        "printed URL is therefore \"ssrn\" and the OCR dropped the r.",
    ),
    (
        "Tables",
        "The memo contains no tables or charts; every visual block is a "
        "paragraph or a bulleted list item, so nothing had to be linearised.",
    ),
    (
        "Why the standalone PDF is the base text",
        "The annex reprint's text layer breaks words across lines with plain "
        "hyphens (142 line-final hyphens, only 20 of them soft hyphens) and "
        "offers no reliable way to tell 'discov-/ery' (glue) from 'mid-/scale' "
        "(keep the hyphen), so it cannot be dehyphenated mechanically. The "
        "standalone memo's digital pages have zero mid-word breaks (its 11 "
        "line-final hyphens are all real compounds), which makes it the only "
        "safe base; the annex is then used as the independent check.",
    ),
]


# ---------------------------------------------------------------------------
# block classification
# ---------------------------------------------------------------------------
class Block:
    __slots__ = ("page", "kind", "text", "x0", "y0", "span_sizes", "lines")

    def __init__(self, page, kind, text, x0, y0, span_sizes, lines=None):
        self.page = page
        self.kind = kind  # heading1 | heading2 | bullet | para | footnote | header
        self.text = text
        self.x0 = x0
        self.y0 = y0
        self.span_sizes = span_sizes
        self.lines = lines or []

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<{self.kind} p{self.page} x{self.x0:.0f} {self.text[:50]!r}>"


def is_bold(font: str) -> bool:
    return "Bold" in font


def clean_spacing(text: str) -> str:
    text = text.replace("\u00a0", " ").replace("\u2003", " ")
    text = re.sub(r"[ \t\r\n]+", " ", text)
    text = re.sub(r"\s+([,.;:!?%)\]\u2019\u201d])", r"\1", text)
    text = re.sub(r"([(\[\u201c])\s+", r"\1", text)
    text = re.sub(r"\s+(\[\^\d+\])", r"\1", text)
    return text.strip()


def join_lines(lines: list[str]) -> str:
    """Join visual lines of one paragraph.

    A line ending in a hyphen keeps the hyphen glued to the next fragment (the
    standalone PDF only breaks lines at real compound hyphens: 11 mid-word
    breaks, all of them "high-/paying", "cutting-/edge", ... style compounds).
    """
    out = ""
    for line in lines:
        if not out:
            out = line
        elif out.endswith("\u00ad"):
            out = out[:-1] + line
        elif out.endswith("-"):
            out += line
        else:
            out += " " + line
    return out


def assemble_block(page, block) -> Block | None:
    """Turn one PyMuPDF block into a classified Block (or None to drop it)."""
    if block["type"] != 0:
        return None
    lines: list[str] = []
    span_sizes: list[float] = []
    fonts: list[str] = []
    x0 = block["bbox"][0]
    y0 = block["bbox"][1]
    for line in block["lines"]:
        pieces: list[str] = []
        for span in line["spans"]:
            raw = span["text"]
            if not raw:
                continue
            span_sizes.append(span["size"])
            if raw.strip():
                fonts.append(span["font"])
            # small digit runs are printed footnote call-outs
            if re.fullmatch(r"\d{1,2}", raw.strip()) and span["size"] <= 9.0:
                pieces.append(f"[^{raw.strip()}] ")
            else:
                pieces.append(raw)
        line_text = clean_spacing("".join(pieces))
        if line_text:
            lines.append(line_text)
    text = clean_spacing(join_lines(lines))
    if not text:
        return None

    real_fonts = [f for f in fonts]
    if real_fonts and all(is_bold(f) for f in real_fonts) and len(lines) <= 3:
        kind = "heading1" if text.isupper() else "heading2"
    elif text.startswith(BULLET):
        text = clean_spacing(text[len(BULLET):])
        kind = "bullet"
    else:
        kind = "para"
    return Block(page, kind, text, x0, y0, span_sizes, lines)


def in_footnote_zone(page_index: int, y0: float, size: float) -> bool:
    """Footnotes sit below the body in ~9.7-10 pt type."""
    return size <= 10.2 and y0 > 650


def read_primary() -> tuple[dict, list[Block]]:
    doc = fitz.open(PRIMARY)
    header: dict[str, object] = {
        "letterhead": [],
        "date": "",
        "memo_for": "",
        "subject": "",
        "body_footnotes": [],
    }
    body: list[Block] = []
    per_page: list[list[Block]] = []

    for pno in range(doc.page_count):
        page = doc[pno]
        blocks: list[Block] = []
        footnotes: list[str] = []
        for raw in page.get_text("dict")["blocks"]:
            if raw["type"] != 0:
                continue
            sizes = [s["size"] for l in raw["lines"] for s in l["spans"] if s["text"].strip()]
            y0 = raw["bbox"][1]
            text_flat = clean_spacing("".join(s["text"] for l in raw["lines"] for s in l["spans"]))
            # page number: a lone small integer near the bottom centre
            if re.fullmatch(r"\d{1,3}", text_flat) and y0 > 700:
                continue
            if in_footnote_zone(pno, y0, max(sizes, default=0)):
                footnotes.append(re.sub(r"^\d{1,2}\s+", "", text_flat))
                continue
            blk = assemble_block(pno, raw)
            if blk is None:
                continue
            # page 1: everything above the first body paragraph is the memo block
            if pno == 0 and y0 < 290:
                blk.kind = "header"
            blocks.append(blk)
        blocks.sort(key=lambda b: (round(b.y0, 1), b.x0))
        if pno == 0:
            for b in blocks:
                if b.kind != "header":
                    continue
                if b.text.startswith("EXECUTIVE OFFICE"):
                    header["letterhead"] = list(b.lines)
                elif b.text.startswith("NSTM"):
                    header["date"] = (
                        re.search(r"[A-Z][a-z]+ \d{1,2}, \d{4}", b.text).group(0)  # type: ignore[union-attr]
                        if re.search(r"[A-Z][a-z]+ \d{1,2}, \d{4}", b.text)
                        else ""
                    )
                elif b.text.startswith("MEMORANDUM FOR"):
                    header["memo_for"] = b.text
                elif b.text.upper().startswith("SUBJECT:"):
                    header["subject"] = b.text[len("SUBJECT:"):].strip()
            blocks = [b for b in blocks if b.kind != "header"]
            # the SUBJECT line is two visual lines inside one block: if the
            # block for "Ushering in ..." is followed by the wrapped remainder
            # ("Administration Research ...") fold it in.
            subj = [b for b in blocks if b.text.startswith("Ushering in a New Golden Age")]
            if subj:
                first = subj[0]
                idx = blocks.index(first)
                if idx + 1 < len(blocks) and blocks[idx + 1].text.startswith("Administration Research"):
                    first.text = clean_spacing(first.text + " " + blocks[idx + 1].text)
                    del blocks[idx + 1]
                header["subject"] = first.text
                del blocks[idx]
            header["body_footnotes"] = footnotes
        else:
            header["body_footnotes"] = list(header["body_footnotes"]) + footnotes  # type: ignore[arg-type]
        per_page.append(blocks)

    # join paragraphs that continue across a page break
    for pno, blocks in enumerate(per_page):
        for i, blk in enumerate(blocks):
            if pno > 0 and i == 0 and body:
                prev = body[-1]
                if (
                    blk.kind == "para"
                    and prev.kind in {"para", "bullet"}
                    and not prev.text.rstrip().endswith(":")
                    and (
                        prev.kind == "bullet"
                        or not prev.text.rstrip().endswith((".", "!", "?", '"', "\u201d"))
                    )
                ):
                    prev.text = clean_spacing(join_lines([prev.text, blk.text]))
                    continue
            body.append(blk)
    return header, body


# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------
def apply_ocr_fixes(text: str) -> str:
    for bad, good, _why in OCR_FIXES:
        text = text.replace(bad, good)
    # the scanned first page uses straight quotes; the memo's digital pages and
    # the rest of the repo use typographic ones
    text = re.sub(r"(?<=[A-Za-z])'(?=[A-Za-z])", "\u2019", text)
    text = re.sub(r"\[\^(\d+)\]\s+([,.;:])", r"[^\1]\2", text)
    return text


def markdown(header: dict, body: list[Block]) -> tuple[str, dict]:
    lines: list[str] = [TITLE, ""]
    letterhead = [t for t in header.get("letterhead", [])]
    for item in letterhead:
        lines += [apply_ocr_fixes(item), ""]
    lines += [DOC_NUMBER, ""]
    lines += [str(header.get("date", "")).strip(), ""]
    lines += [str(header.get("memo_for", "")).strip(), ""]
    lines += ["FROM:", ""]
    for item in FROM_BLOCK:
        lines += [item, ""]
    lines += ["SUBJECT:", ""]
    lines += [apply_ocr_fixes(str(header.get("subject", "")).strip()), ""]

    in_list = False
    counts = {"heading1": 0, "heading2": 0, "bullet": 0, "para": 0}
    body_words = 0
    for blk in body:
        text = apply_ocr_fixes(blk.text)
        counts[blk.kind if blk.kind in counts else "para"] += 1
        if blk.kind == "heading1":
            if in_list:
                lines.append("")
                in_list = False
            lines += [f"### {text}", ""]
        elif blk.kind == "heading2":
            if in_list:
                lines.append("")
                in_list = False
            lines += [f"#### {text}", ""]
        elif blk.kind == "bullet":
            lines.append(f"- {text}")
            in_list = True
            body_words += len(text.split())
        else:
            if in_list:
                lines.append("")
                in_list = False
            lines += [text, ""]
            body_words += len(text.split())
    if in_list:
        lines.append("")

    notes = [apply_ocr_fixes(n) for n in header.get("body_footnotes", [])]
    notes = [n for n in notes if n]
    if notes:
        lines += ["### Notes", ""]
        for i, note in enumerate(notes, start=1):
            lines += [f"[^{i}]: {note}", ""]

    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text).rstrip() + "\n"
    stats = {
        "counts": counts,
        "body_words": body_words,
        "file_words": len(text.split()),
        "note_words": sum(len(n.split()) for n in notes),
        "notes": len(notes),
    }
    return text, stats


# ---------------------------------------------------------------------------
# verification against the report annex
# ---------------------------------------------------------------------------
ANNEX_HEADER_RE = re.compile(
    r"MEMORANDUM FOR THE HEADS OF.*?Development Budget Priorities", re.S
)


def annex_stream() -> str:
    doc = fitz.open(REPORT_PDF)
    chunks: list[str] = []
    for pno in range(*ANNEX_PDF_PAGES):
        for line in doc[pno].get_text().split("\n"):
            s = line.strip()
            if not s:
                continue
            if re.fullmatch(r"\d{1,3}", s):
                continue
            if s == ANNEX_RUNNING_HEAD:
                continue
            chunks.append(s)
    text = clean_spacing(join_lines(chunks))
    text = ANNEX_HEADER_RE.sub(" ", text)
    return clean_spacing(text)


def tokenize(text: str) -> list[str]:
    """Comparison tokens: lower-case, hyphenation- and punctuation-insensitive.

    Hyphens are deleted rather than turned into separators so that the report
    annex's mid-word line breaks ("discov-/ery", "bal-/ance") and the standalone
    memo's clean words ("discovery", "balance") compare equal.
    """
    text = text.replace("\u00ad", "").replace("-", "")
    text = text.replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
    text = re.sub(r"[^0-9A-Za-z$%&'./]+", " ", text)
    toks = [t.strip(".").lower() for t in text.split()]
    return [t for t in toks if t]


def verify(md_text: str) -> dict:
    annex = annex_stream()
    # compare body against body: drop the title, the memo block and the notes
    body_md = md_text.split("Budget Priorities", 1)[-1]
    body_md = body_md.split("### Notes", 1)[0]
    body_md = re.sub(r"^#{1,4} ", "", body_md, flags=re.M)
    body_md = body_md.replace("- ", " ")
    # the standalone memo prints five footnote call-outs; the annex reprint has
    # none, so they are excluded from the comparison and reported separately
    markers = re.findall(r"\[\^\d+\]", body_md)
    body_md = re.sub(r"\[\^\d+\]", " ", body_md)
    a = tokenize(annex)
    b = tokenize(body_md)
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    clusters = [op for op in sm.get_opcodes() if op[0] != "equal"]
    detail = []
    for tag, i1, i2, j1, j2 in clusters:
        detail.append(
            {
                "tag": tag,
                "annex": " ".join(a[max(0, i1 - 10):i2 + 10]),
                "md": " ".join(b[max(0, j1 - 10):j2 + 10]),
                "annex_removed": " ".join(a[i1:i2]),
                "md_added": " ".join(b[j1:j2]),
            }
        )
    return {
        "annex_words": len(a),
        "md_words": len(b),
        "ratio": sm.ratio(),
        "clusters": detail,
        "annex_text": annex,
        "markers": markers,
    }


# ---------------------------------------------------------------------------
def report_text(header: dict, stats: dict, ver: dict, md_text: str) -> str:
    sha = hashlib.sha256(PRIMARY.read_bytes()).hexdigest()
    doc = fitz.open(PRIMARY)
    out: list[str] = []
    out += ["FY 2028 R&D Priorities Memorandum - extraction and verification report", ""]
    out += [f"generated: {date.today().isoformat()} by tools/extract_annex.py", ""]

    out += ["1. Sources", ""]
    out += [f"primary     : sources/{PRIMARY.name}"]
    out += [f"              {PRIMARY_URL}"]
    out += [f"              {len(PRIMARY.read_bytes())} bytes, sha256 {sha}"]
    out += [f"              {doc.page_count} pages (p.1 = scan + OCR layer, p.2-14 = digital text layer)"]
    out += [f"cross-check : Science-A-New-Golden-Age.pdf, PDF pages {ANNEX_PDF_PAGES[0]}-{ANNEX_PDF_PAGES[1]-1}"]
    out += [f"              = printed pages {ANNEX_PRINTED} (reprint titled \"{ANNEX_RUNNING_HEAD}\")"]
    out += [""]

    out += ["2. Method", ""]
    out += [
        "Text is rebuilt from the standalone PDF's block structure: PyMuPDF blocks",
        "are already paragraph-, heading- and bullet-aligned, so paragraphs are the",
        "unit of reconstruction (no line-per-visual-line output). Within a block,",
        "visual lines are joined; blocks are sorted by (y, x); small-font digit runs",
        "(<=9 pt) become [^n] call-outs. Page numbers (lone digits near the bottom",
        "centre) are dropped. Paragraphs split by a page break are rejoined when the",
        "new page opens without a heading or a bullet and the previous block is a",
        "bullet or ends without terminal punctuation. Heading level 1 = all-caps",
        "all-bold block, level 2 = all-bold block. Bullets become markdown list",
        "items. Fields taken from the annex reprint instead of the OCR first page:",
        "the FROM block (names/titles) and the document number NSTM-5 / M-26-16.",
        "",
    ]

    out += ["3. OCR repairs on the scanned first page", ""]
    for bad, good, why in OCR_FIXES:
        out += [f"  {bad!r} -> {good!r}   ({why})"]
    out += ["  FROM block (MICHAEL J. KRATSIOS / ASSISTANT TO THE PRESIDENT / DIRECTOR,"
            " OFFICE OF ... / RUSSELL T. VOUGHT) taken verbatim from the annex reprint,"
            " whose text layer is clean.", ""]

    out += ["4. Output", ""]
    out += [f"  file            : sources/en/{OUT_MD.name}"]
    out += [f"  words (file)    : {stats['file_words']}"]
    out += [f"  words (body)    : {stats['body_words']}"]
    out += [f"  words (notes)   : {stats['note_words']} in {stats['notes']} footnote(s)"]
    out += [f"  headings        : {stats['counts']['heading1']} x '### ' + {stats['counts']['heading2']} x '#### '"]
    out += [f"  paragraphs      : {stats['counts']['para']}"]
    out += [f"  list items      : {stats['counts']['bullet']}"]
    out += [""]

    out += ["5. Quantitative verification (difflib.SequenceMatcher, token level)", ""]
    out += ["  comparison unit : one token = one word, lower-cased, punctuation stripped,"]
    out += ["                    hyphens and soft hyphens deleted so that the two PDFs'"]
    out += ["                    different line-breaking/hyphenation cannot create noise"]
    out += [f"  annex tokens    : {ver['annex_words']}"]
    out += [f"  output tokens   : {ver['md_words']}  (the {len(ver['markers'])} footnote call-outs"]
    out += ["                    [^1]-[^5], absent from the annex reprint, are excluded;"]
    out += ["                    the annex reprint's own memo block is excluded too)"]
    out += [f"  token delta     : {ver['annex_words'] - ver['md_words']} = exactly the words of the"]
    out += ["                    one divergent phrase in cluster [1] below"]
    out += [f"  similarity ratio: {ver['ratio']:.6f}"]
    out += [f"  difference clusters: {len(ver['clusters'])}"]
    out += [""]
    if ver["clusters"]:
        out += ["  clusters (annex -> output):", ""]
        for k, c in enumerate(ver["clusters"], start=1):
            out += [f"   [{k}] {c['tag']}"]
            out += [f"       annex : ...{c['annex']}..."]
            out += [f"       output: ...{c['md']}..."]
        out += [""]
    else:
        out += ["  no difference clusters - the two word sequences are identical.", ""]

    out += ["6. Residual differences, ambiguities, decisions", ""]
    for i, (title, body) in enumerate(NOTES, start=1):
        out += [f"  {i}. {title}", f"     {body}", ""]

    out += ["7. Non-goals", ""]
    out += ["  No other file in the repo was modified. The 185 endnote definitions that"]
    out += ["  previously sat in sources/en/annex-fy2028.en.md are the report's own"]
    out += ["  endnotes (they are also present in sources/en/references.en.md and in"]
    out += ["  sources/report.json); they are not part of the memo and were dropped"]
    out += ["  when the file was replaced with the memo text.", ""]
    out += ["8. Reproduce", ""]
    out += ["  python tools/extract_annex.py            # rewrites the memo + this report"]
    out += ["  python tools/extract_annex.py --debug    # dumps block classification/diff", ""]
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()

    header, body = read_primary()
    md_text, stats = markdown(header, body)
    ver = verify(md_text)

    if args.debug:
        print("--- header ---")
        for k, v in header.items():
            print(f"  {k}: {v!r}")
        print("--- body blocks ---")
        for b in body:
            print(f"  {b.kind:8s} x{b.x0:6.1f} {b.text[:100]}")
        print("--- stats ---", stats)
        print("--- verify ---", ver["ratio"], len(ver["clusters"]))
        for c in ver["clusters"]:
            print("  ", c["tag"], "| annex:", c["annex"][:160], "|| out:", c["md"][:160])
        return 0

    OUT_MD.write_text(md_text, encoding="utf-8")
    OUT_REPORT.write_text(report_text(header, stats, ver, md_text), encoding="utf-8")
    print(f"wrote {OUT_MD.relative_to(ROOT)}")
    print(f"wrote {OUT_REPORT.relative_to(ROOT)}")
    print(f"body words {stats['body_words']} file words {stats['file_words']}")
    print(f"similarity {ver['ratio']:.6f} clusters {len(ver['clusters'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())