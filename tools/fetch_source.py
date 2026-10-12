#!/usr/bin/env python3
"""Fetch the official web edition of the report and cache the raw HTML."""
from __future__ import annotations

import pathlib
import sys

import requests

URL = "https://www.whitehouse.gov/science/"
OUT = pathlib.Path(__file__).resolve().parents[1] / "sources" / "whitehouse-science.html"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


def main() -> None:
    response = requests.get(URL, headers=HEADERS, timeout=120)
    response.raise_for_status()
    response.encoding = "utf-8"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(response.text, encoding="utf-8")
    print(f"saved {len(response.text)} bytes to {OUT}")


if __name__ == "__main__":
    sys.exit(main())