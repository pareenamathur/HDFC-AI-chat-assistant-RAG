#!/usr/bin/env python3
"""Sanity + freshness validation after corpus refresh (local or GHA)."""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "corpus_version.json"
FETCH_MANIFEST = ROOT / "data" / "fetch_manifest.json"
CHUNKED = ROOT / "data" / "processed" / "chunked_data_phase1.4.json"
CHROMA = ROOT / "data" / "indexed" / "chroma.sqlite3"
_NAV_RE = re.compile(r"NAV:\s*\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2}\b", re.I)
_MAX_FETCH_FAIL_PCT = 20.0

sys.path.insert(0, str(ROOT))
from backend.corpus_diagnostics import STALE_NAV_FAIL_DAYS, build_freshness_report  # noqa: E402

_STALE_NAV_DAYS = STALE_NAV_FAIL_DAYS


def _check_fetch_manifest() -> tuple[bool, list[str]]:
    warnings: list[str] = []
    if not FETCH_MANIFEST.is_file():
        warnings.append("missing fetch_manifest.json — run Phase 1.1 fetcher")
        return False, warnings
    with open(FETCH_MANIFEST, encoding="utf-8") as f:
        data = json.load(f)
    entries = data.get("entries") or []
    if not entries:
        warnings.append("fetch_manifest has no entries")
        return False, warnings
    failed = [e for e in entries if e.get("error")]
    fail_pct = 100.0 * len(failed) / len(entries)
    print(f"fetch_manifest: {len(entries)} URLs, failed={len(failed)} ({fail_pct:.1f}%)")
    if fail_pct > _MAX_FETCH_FAIL_PCT:
        warnings.append(f"fetch failure rate {fail_pct:.1f}% exceeds {_MAX_FETCH_FAIL_PCT}%")
        for e in failed[:5]:
            print("  FAIL", e.get("url"), e.get("error"))
    no_nav = [e for e in entries if not e.get("error") and not e.get("nav_as_of")]
    if no_nav:
        warnings.append(f"{len(no_nav)} pages fetched but NAV not extracted (__NEXT_DATA__)")
    stale = [e for e in entries if e.get("nav_stale")]
    if stale:
        print(f"WARN: {len(stale)} funds have NAV older than 3 days on Groww")
        for e in stale[:3]:
            print(
                "  stale",
                e.get("scheme_name"),
                "nav_as_of",
                e.get("nav_as_of"),
                "age_days",
                e.get("nav_age_days"),
            )
    return len(warnings) == 0, warnings


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
        https_meta = sum(
            1
            for c in chunks
            if str((c.get("metadata") or {}).get("source_url", "")).startswith("https://")
        )
        print(f"chunks with NAV line: {nav_hits}/{len(chunks)}")
        print(f"chunks with https source_url: {https_meta}/{len(chunks)}")
        if chunks:
            sample = next((c for c in chunks if _NAV_RE.search(c.get("text") or "")), chunks[0])
            m2 = _NAV_RE.search(sample.get("text") or "")
            if m2:
                print("sample NAV snippet:", m2.group(0))

    fetch_ok, fetch_warnings = _check_fetch_manifest()
    if not fetch_ok:
        ok = False
        for w in fetch_warnings:
            print("FAIL:", w)

    report = build_freshness_report(ROOT, stale_nav_days=_STALE_NAV_DAYS)
    print(
        "NAV as-of range:",
        report.get("nav_as_of_min"),
        "to",
        report.get("nav_as_of_max"),
        "| age_days=",
        report.get("nav_age_days"),
    )
    if report.get("embedding_model_mismatch"):
        print("FAIL: manifest embedding != MiniLM")
        ok = False
    if report.get("nav_stale_warning"):
        print(
            "FAIL: newest NAV in corpus is",
            report.get("nav_age_days"),
            "days old (threshold",
            report.get("stale_nav_threshold_days"),
            ") — check Groww/AMFI fetch_manifest",
        )
        ok = False
    today = datetime.now(timezone.utc).date()
    print("validation_date_utc:", today.isoformat())
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
