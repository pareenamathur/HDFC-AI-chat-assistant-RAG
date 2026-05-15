#!/usr/bin/env python3
"""
Full corpus refresh for Milestone2 (fetch → chunk → Chroma with MiniLM).

Usage (from Milestone2/):
  python scripts/run_corpus_refresh.py
  python scripts/run_corpus_refresh.py --skip-fetch   # reuse data/html/*.html

Used by .github/workflows/corpus-refresh.yml on schedule / manual dispatch.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.corpus_diagnostics import collect_nav_dates_from_chunks  # noqa: E402

os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

ROOT = Path(__file__).resolve().parents[1]


def _run(desc: str, script: Path, timeout_s: int = 3600) -> None:
    print(f"\n=== {desc} ===", flush=True)
    if not script.is_file():
        raise FileNotFoundError(script)
    r = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(ROOT),
        timeout=timeout_s,
    )
    if r.returncode != 0:
        raise RuntimeError(f"{desc} failed (exit {r.returncode})")


def _write_manifest() -> None:
    chunked = ROOT / "data" / "processed" / "chunked_data_phase1.4.json"
    n_chunks = 0
    schemes: set[str] = set()
    nav_dates: list[str] = []
    fetch_stats: dict = {}
    fetch_path = ROOT / "data" / "fetch_manifest.json"
    if fetch_path.is_file():
        try:
            with open(fetch_path, encoding="utf-8") as f:
                fm = json.load(f)
            entries = fm.get("entries") or []
            ok = [e for e in entries if not e.get("error")]
            fetch_stats = {
                "urls_total": len(entries),
                "urls_ok": len(ok),
                "urls_failed": len(entries) - len(ok),
                "nav_stale_count": sum(1 for e in ok if e.get("nav_stale")),
            }
        except (OSError, json.JSONDecodeError):
            pass
    if chunked.is_file():
        with open(chunked, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            n_chunks = len(data)
            for c in data:
                sn = (c.get("scheme_name") or (c.get("metadata") or {}).get("scheme_name") or "")
                if sn:
                    schemes.add(str(sn))
            nav_sorted = sorted(collect_nav_dates_from_chunks(data))
            nav_dates = [d.isoformat() for d in nav_sorted]

    manifest = {
        "version": f"corpus-v{datetime.now(timezone.utc).strftime('%Y.%m.%d')}",
        "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "phases_run": ["1.1", "1.2", "1.3", "1.4", "rebuild_chroma"],
        "source": "github_actions_refresh" if os.getenv("GITHUB_ACTIONS") else "local_refresh",
        "chunks_total": n_chunks,
        "schemes_count": len(schemes),
        "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
        "vector_store": "ChromaDB",
        "collection_name": "mf_faq_corpus",
        "nav_as_of_dates": nav_dates,
        "nav_as_of_max": nav_dates[-1] if nav_dates else None,
        "fetch_stats": fetch_stats,
    }
    out = ROOT / "data" / "corpus_version.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"Wrote {out} ({n_chunks} chunks, {len(schemes)} schemes)", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-fetch", action="store_true", help="Skip Phase 1.1 (use existing HTML)")
    args = ap.parse_args()

    phases = [
        ("1.2 Extract", ROOT / "phase1_ingestion_corpus_build/subphase1.2_extractor/src/run_extractor.py"),
        ("1.3 Clean", ROOT / "phase1_ingestion_corpus_build/subphase1.3_cleaner_normalizer/src/run_cleaner.py"),
        ("1.4 Chunk", ROOT / "phase1_ingestion_corpus_build/subphase1.4_chunker/src/run_chunker.py"),
    ]
    if not args.skip_fetch:
        phases.insert(
            0,
            ("1.1 Fetch", ROOT / "phase1_ingestion_corpus_build/subphase1.1_fetcher/src/run_fetcher.py"),
        )

    for desc, path in phases:
        _run(desc, path)

    print("\n=== Rebuild Chroma (MiniLM) ===", flush=True)
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts/rebuild_chroma_from_chunks.py"), "--force"],
        cwd=str(ROOT),
        timeout=7200,
    )
    if r.returncode != 0:
        raise RuntimeError("rebuild_chroma_from_chunks.py failed")

    _write_manifest()
    print("\nCorpus refresh complete.", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        raise SystemExit(1)
