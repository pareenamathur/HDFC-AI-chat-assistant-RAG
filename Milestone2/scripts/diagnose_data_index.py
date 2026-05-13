#!/usr/bin/env python3
"""
Print a one-screen diagnostic for Chroma + processed data (Railway / local).
Run from repo root:  python Milestone2/scripts/diagnose_data_index.py
Or from Milestone2/: python scripts/diagnose_data_index.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _milestone2_root() -> Path:
    here = Path(__file__).resolve()
    # .../Milestone2/scripts/diagnose_data_index.py -> Milestone2
    return here.parents[1]


def main() -> None:
    root = _milestone2_root()
    indexed = root / "data" / "indexed"
    processed = root / "data" / "processed"
    chunked = processed / "chunked_data_phase1.4.json"

    indexed_exists = indexed.is_dir()
    processed_exists = processed.is_dir()
    chunked_exists = chunked.is_file()

    files_in_indexed: list[str] = []
    if indexed_exists:
        try:
            for p in sorted(indexed.iterdir()):
                rel = p.name
                if p.is_dir():
                    files_in_indexed.append(f"{rel}/")
                else:
                    files_in_indexed.append(rel)
        except OSError as e:
            files_in_indexed = [f"<error listing: {e}>"]

    indexed_empty = True
    if indexed_exists:
        try:
            non_readme = [p for p in indexed.iterdir() if p.name != "README.md"]
            indexed_empty = len(non_readme) == 0
        except OSError:
            indexed_empty = True

    sqlite_ok = (indexed / "chroma.sqlite3").is_file() if indexed_exists else False

    chunk_count = 0
    if chunked_exists:
        try:
            with open(chunked, encoding="utf-8") as f:
                data = json.load(f)
            chunk_count = len(data) if isinstance(data, list) else 0
        except Exception as e:
            chunk_count = -1
            err = str(e)
        else:
            err = ""

    print("=== Milestone2 data / Chroma diagnostic ===")
    print(f"MILESTONE2_ROOT: {root}")
    print(f"INDEXED_FOLDER_EXISTS: {indexed_exists}")
    print(f"INDEXED_FOLDER_EMPTY (no Chroma files aside README): {indexed_empty}")
    print(f"CHROMA_SQLITE_PRESENT: {sqlite_ok}")
    print(f"PROCESSED_FOLDER_EXISTS: {processed_exists}")
    print(f"CHUNKED_JSON_EXISTS: {chunked_exists}")
    if chunked_exists and chunk_count >= 0:
        print(f"CHUNKS_IN_JSON: {chunk_count}")
    elif chunked_exists:
        print(f"CHUNKS_IN_JSON: error reading — {err}")
    print(f"FILES_FOUND_IN_INDEXED ({len(files_in_indexed)}):")
    for name in files_in_indexed[:80]:
        print(f"  - {name}")
    if len(files_in_indexed) > 80:
        print(f"  ... and {len(files_in_indexed) - 80} more")

    # Optional Chroma count
    if sqlite_ok:
        try:
            import chromadb

            client = chromadb.PersistentClient(path=str(indexed))
            col = client.get_collection("mf_faq_corpus")
            print(f"CHROMA_COLLECTION mf_faq_corpus COUNT: {col.count()}")
        except Exception as e:
            print(f"CHROMA_OPEN_ERROR: {e}")
    else:
        print("CHROMA_COLLECTION: (skipped — no sqlite DB)")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("FATAL", file=sys.stderr)
        raise
