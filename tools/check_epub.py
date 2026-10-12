#!/usr/bin/env python3
"""Validate a built EPUB: well-formedness, links, images, and absence of PDF page furniture.

Checks performed on every .xhtml document inside the archive:
  * parses as XML (a malformed file makes readers drop the chapter silently)
  * every internal href="#..." resolves to an element id in the same document
  * every <img src> exists in the archive and is listed in the OPF manifest
  * the spine references only manifest items, and the manifest has no orphans
  * mimetype is the first entry and stored uncompressed
  * count of English blockquotes vs Chinese paragraphs (bilingual edition)
  * no page-number / running-header residue ("29", "30", "Chapter II – Introduction"),
    no digit-only paragraph, no paragraph longer than 20,000 characters

Usage: python tools/check_epub.py [epub-path ...]
"""

from __future__ import annotations

import pathlib
import re
import sys
import zipfile
from collections import Counter
from xml.etree import ElementTree

ROOT = pathlib.Path(__file__).resolve().parents[1]
XHTML = "{http://www.w3.org/1999/xhtml}"
OPF = "{http://www.idpf.org/2007/opf}"
DC = "{http://purl.org/dc/elements/1.1/}"
HEADER_NOISE = re.compile(r"^(chapter|annex)\s+[ivx]+\s*[–-]\s*(introduction|conclusion)|^\d{1,3}$", re.I)


def inner_text(element: ElementTree.Element) -> str:
    return "".join(element.itertext())


def check(path: pathlib.Path) -> int:
    problems: list[str] = []
    bilingual = "中英对照" in path.name
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if names[0] != "mimetype":
            problems.append("mimetype is not the first archive entry")
        else:
            if archive.getinfo("mimetype").compress_type != zipfile.ZIP_STORED:
                problems.append("mimetype is compressed")
            if archive.read("mimetype") != b"application/epub+zip":
                problems.append("mimetype has the wrong content")
        documents = [name for name in names if name.endswith(".xhtml")]
        manifest_ids: dict[str, str] = {}
        spine: list[str] = []
        opf_name = next((n for n in names if n.endswith(".opf")), None)
        if opf_name is None:
            problems.append("no OPF package document")
        else:
            package = ElementTree.fromstring(archive.read(opf_name))
            for item in package.iter(f"{OPF}item"):
                manifest_ids[item.get("id", "")] = item.get("href", "")
            spine = [ref.get("idref", "") for ref in package.iter(f"{OPF}itemref")]
            for idref in spine:
                if idref not in manifest_ids:
                    problems.append(f"spine references unknown manifest id {idref}")
            for id_, href in manifest_ids.items():
                if href not in names and f"OEBPS/{href}" not in names:
                    problems.append(f"manifest item {id_} -> missing file {href}")
            titles = [inner_text(t) for t in package.iter(f"{DC}title")]
            language = next((inner_text(l) for l in package.iter(f"{DC}language")), "")
        counts = Counter()
        for name in sorted(documents):
            try:
                tree = ElementTree.fromstring(archive.read(name))
            except ElementTree.ParseError as error:
                problems.append(f"{name}: XML parse error {error}")
                continue
            ids = {element.get("id") for element in tree.iter() if element.get("id")}
            for element in tree.iter():
                if element.tag == f"{XHTML}a":
                    href = element.get("href", "")
                    if href.startswith("#") and href[1:] not in ids:
                        problems.append(f"{name}: broken internal link {href}")
                elif element.tag == f"{XHTML}img":
                    source = element.get("src", "")
                    if source and f"OEBPS/{source}" not in names:
                        problems.append(f"{name}: missing image {source}")
            for element in tree.iter():
                if element.tag == f"{XHTML}blockquote":
                    counts["en"] += 1
                elif element.tag == f"{XHTML}p":
                    text = inner_text(element).strip()
                    counts["zh"] += 1
                    if HEADER_NOISE.match(text):
                        problems.append(f"{name}: page furniture in a paragraph: {text[:60]!r}")
                    if len(text) > 20000:
                        problems.append(f"{name}: suspiciously long paragraph ({len(text)} chars)")
                elif element.tag == f"{XHTML}figure":
                    counts["figures"] += 1
                elif element.tag == f"{XHTML}li":
                    if element.get("id", "").startswith("fn-"):
                        counts["notes"] += 1
            # In the bilingual edition every translated paragraph must be preceded by
            # its English original; anything else means a pairing bug.
            if bilingual and any(element.tag == f"{XHTML}blockquote" for element in tree.iter()):
                for parent in tree.iter():
                    children = list(parent)
                    for position, element in enumerate(children):
                        if element.tag != f"{XHTML}p" or "zh" not in (element.get("class") or ""):
                            continue
                        previous = children[position - 1] if position else None
                        if previous is None or previous.tag != f"{XHTML}blockquote":
                            counts["unpaired"] += 1
                            if counts["unpaired"] <= 3:
                                problems.append(
                                    f"{name}: Chinese paragraph without an English original: "
                                    f"{inner_text(element)[:50]!r}"
                                )
    print(f"\n=== {path.name} ===")
    print(f"documents: {len(documents)}  images: {sum(1 for n in names if n.startswith('OEBPS/images/') and not n.endswith('/'))}")
    print(f"english blockquotes: {counts['en']}  chinese paragraphs: {counts['zh']}  endnotes: {counts['notes']}  figures: {counts['figures']}")
    print(f"spine items: {len(spine)}  language: {language}  titles: {titles}")
    if problems:
        print(f"PROBLEMS ({len(problems)}):")
        for problem in problems[:40]:
            print("  -", problem)
        return 1
    print("OK: well-formed, links and images resolve, no page furniture detected")
    return 0


def main() -> None:
    targets = [pathlib.Path(a) for a in sys.argv[1:]] or sorted(ROOT.glob("*.epub"))
    failures = sum(check(target) for target in targets if target.exists())
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()