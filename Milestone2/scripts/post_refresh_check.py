#!/usr/bin/env python3
"""Quick sanity check after corpus refresh (local or GHA)."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "corpus_version.json"
CHUNKED = ROOT / "data" / "processed" / "chunked_data_phase1.4.json"
CHROMA = ROOT / "data" / "indexed" / "chroma.sqlite3"
_NAV_RE = re.compile(r"NAV:\s*\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2}\b", re.I)


def main() -> int:
    ok = True
    if not MANIFEST.is_file():
        print("FAIL: missing", MANIFEST)
        return 1
    with open(MANIFEST, encoding="utf-8") as f:
        m = json.load(f)
    print("corpus_version.json:", m.get("last_updated"), "| chunks:", m.get("chunks_total"))
    if not CHROMA.is_file():
        print("FAIL: missing", CHROMA)
        ok = False
    else:
        print("chroma.sqlite3:", CHROMA.stat().st_size, "bytes")
    if CHUNKED.is_file():
        with open(CHUNKED, encoding="utf-8") as f:
            chunks = json.load(f)
        nav_hits = sum(1 for c in chunks if _NAV_RE.search(c.get("text") or ""))
        print(f"chunks with NAV line: {nav_hits}/{len(chunks)}")
        if chunks:
            sample = next((c for c in chunks if _NAV_RE.search(c.get("text") or "")), chunks[0])
            m2 = _NAV_RE.search(sample.get("text") or "")
            if m2:
                print("sample NAV snippet:", m2.group(0))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
