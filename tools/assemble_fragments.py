#!/usr/bin/env python3
"""Assemble a chapter that was translated in parallel fragments.

Fragments are `sources/zh/_<slug>.<A|B|C|D>.zh.md`, each mirroring an exact line range
of the English file (checked with tools/check_part.py). This tool concatenates them in
order into `sources/zh/<slug>.zh.md` and reports the block accounting against the
English source; use `--check` for a dry run that writes nothing.

Usage:
  python tools/assemble_fragments.py chapter-02 --check
  python tools/assemble_fragments.py chapter-02
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_bilingual import markers, parse_blocks  # noqa: E402

ZH = ROOT / "sources" / "zh"


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    slug = sys.argv[1]
    dry_run = "--check" in sys.argv
    fragments = sorted(ZH.glob(f"_{slug}.*.zh.md"))
    if not fragments:
        sys.exit(f"no fragments found for {slug}")
    blocks: list[str] = []
    for fragment in fragments:
        for line in fragment.read_text(encoding="utf-8").splitlines():
            if line.strip():
                blocks.append(line.strip())
    english = parse_blocks(ROOT / "sources" / "en" / f"{slug}.en.md")
    print(f"fragments: {', '.join(f.name for f in fragments)}")
    print(f"english blocks: {len(english)}  assembled blocks: {len(blocks)}")
    if len(blocks) != len(english):
        print(f"MISMATCH: {len(english) - len(blocks)} block(s) short")
    target = ZH / f"{slug}.zh.md"
    if dry_run:
        print("dry run: nothing written")
        return
    target.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")
    print(f"wrote {target.relative_to(ROOT)}")
    note_numbers = sorted({int(n) for block in blocks for n in markers(block)})
    print(f"endnote markers in the assembled text: {note_numbers[0]}–{note_numbers[-1]} ({len(note_numbers)} notes)")


if __name__ == "__main__":
    main()