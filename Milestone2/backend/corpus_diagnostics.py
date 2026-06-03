"""Corpus manifest + NAV freshness helpers (startup logs, health, post-refresh check)."""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

_NAV_RE = re.compile(
    r"NAV:\s*(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{2})\b",
    re.IGNORECASE,
)
_MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}
_EXPECTED_EMBEDDING = "sentence-transformers/all-MiniLM-L6-v2"
STALE_NAV_FAIL_DAYS = 7


def parse_nav_token(token: str) -> Optional[date]:
    m = _NAV_RE.search(token or "")
    if not m:
        return None
    day = int(m.group(1))
    mon = _MONTHS.get(m.group(2).lower()[:3])
    if not mon:
        return None
    yy = int(m.group(3))
    year = 2000 + yy if yy < 100 else yy
    try:
        return date(year, mon, day)
    except ValueError:
        return None


def collect_nav_dates_from_chunks(chunks: List[Dict[str, Any]]) -> Set[date]:
    found: Set[date] = set()
    for c in chunks:
        text = c.get("text") or ""
        for m in _NAV_RE.finditer(text):
            d = parse_nav_token(m.group(0))
            if d:
                found.add(d)
        for bag in (c.get("metadata"), c.get("structured_data")):
            if isinstance(bag, dict):
                d = parse_iso_nav_date(bag.get("nav_as_of"))
                if d:
                    found.add(d)
    return found


def parse_iso_nav_date(raw: Any) -> Optional[date]:
    if not raw:
        return None
    s = str(raw).strip()[:10]
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def collect_nav_dates_from_fetch_manifest(manifest: Dict[str, Any]) -> Set[date]:
    found: Set[date] = set()
    for e in manifest.get("entries") or []:
        if e.get("error"):
            continue
        d = parse_iso_nav_date(e.get("nav_as_of"))
        if d:
            found.add(d)
    return found


def compute_nav_as_of_max(
    chunks: List[Dict[str, Any]],
    fetch_manifest: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[date], List[str]]:
    """Union NAV dates from chunk text, metadata, and fetch_manifest."""
    sources: List[str] = []
    found: Set[date] = set()
    if chunks:
        from_chunks = collect_nav_dates_from_chunks(chunks)
        if from_chunks:
            found |= from_chunks
            sources.append("chunks")
    if fetch_manifest:
        from_fetch = collect_nav_dates_from_fetch_manifest(fetch_manifest)
        if from_fetch:
            found |= from_fetch
            sources.append("fetch_manifest")
    if not found:
        return None, sources
    return max(found), sources


def load_manifest(base_dir: Path) -> Optional[Dict[str, Any]]:
    path = base_dir / "data" / "corpus_version.json"
    if not path.is_file():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def load_chunked_file(base_dir: Path) -> Tuple[List[Dict[str, Any]], int]:
    path = base_dir / "data" / "processed" / "chunked_data_phase1.4.json"
    if not path.is_file():
        return [], 0
    try:
        with open(path, encoding="utf-8") as f:
            chunks = json.load(f)
    except (OSError, json.JSONDecodeError):
        return [], 0
    if not isinstance(chunks, list):
        return [], 0
    return chunks, len(chunks)


def load_fetch_manifest(base_dir: Path) -> Optional[Dict[str, Any]]:
    path = base_dir / "data" / "fetch_manifest.json"
    if not path.is_file():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def load_chunked_nav_dates(base_dir: Path) -> Tuple[Set[date], int]:
    chunks, count = load_chunked_file(base_dir)
    if not chunks:
        return set(), count
    fetch_manifest = load_fetch_manifest(base_dir)
    nav_max, _ = compute_nav_as_of_max(chunks, fetch_manifest)
    found = collect_nav_dates_from_chunks(chunks)
    if fetch_manifest:
        found |= collect_nav_dates_from_fetch_manifest(fetch_manifest)
    return found, count


def build_corpus_coverage_report(base_dir: Path) -> Dict[str, Any]:
    """Per-fund coverage flags for holdings, TER, NAV, and latest dates (startup / CI)."""
    chunks, _ = load_chunked_file(base_dir)
    if not chunks:
        return {"funds": [], "total_chunks": 0}

    _holdings_re = re.compile(r"Holdings\s*\(\s*\d+\s*\)", re.I)
    _expense_re = re.compile(
        r"(?:Total Expense Ratio|Expense Ratio|TER:|expense_ratio\s+[\d.])", re.I
    )
    _nav_re = re.compile(r"NAV:\s*\d", re.I)
    _alloc_re = re.compile(r"asset allocation|hybrid dynamic|equity flexi", re.I)

    by_scheme: Dict[str, List[Dict[str, Any]]] = {}
    for c in chunks:
        sn = c.get("scheme_name") or (c.get("metadata") or {}).get("scheme_name") or "?"
        by_scheme.setdefault(sn, []).append(c)

    funds: List[Dict[str, Any]] = []
    for scheme, sch_chunks in sorted(by_scheme.items()):
        flags = {
            "holdings": False,
            "allocation": False,
            "expense_ratio": False,
            "nav": False,
        }
        latest: Optional[str] = None
        source_url = None
        for c in sch_chunks:
            text = c.get("text") or ""
            if _holdings_re.search(text):
                flags["holdings"] = True
            if _alloc_re.search(text, re.I):
                flags["allocation"] = True
            if _expense_re.search(text):
                flags["expense_ratio"] = True
            sd = c.get("structured_data") or {}
            md = c.get("metadata") or {}
            if sd.get("expense_ratio") or md.get("expense_ratio"):
                flags["expense_ratio"] = True
            if _nav_re.search(text):
                flags["nav"] = True
            nd = parse_iso_nav_date(md.get("nav_as_of") or sd.get("nav_as_of"))
            if not nd:
                for m in _NAV_RE.finditer(text):
                    d = parse_nav_token(m.group(0))
                    if d:
                        nd = d
                        break
            if nd:
                iso = nd.isoformat()
                if latest is None or iso > latest:
                    latest = iso
            if not source_url:
                u = md.get("source_url") or md.get("page_url")
                if u and str(u).startswith("http"):
                    source_url = u
        risk_present = any(
            (c.get("metadata") or {}).get("risk_level")
            or (c.get("structured_data") or {}).get("risk_level")
            or re.search(r"Risk level:", c.get("text") or "", re.I)
            for c in sch_chunks
        )
        aum_val = None
        for c in sch_chunks:
            for bag in (c.get("structured_data"), c.get("metadata")):
                if isinstance(bag, dict) and bag.get("aum"):
                    aum_val = str(bag.get("aum"))
                    break
            if aum_val:
                break
        funds.append(
            {
                "fund_name": scheme.replace(" Direct Growth", "").replace(" Direct Plan Growth", ""),
                "scheme_name": scheme,
                "source_url": source_url,
                "expense_ratio": flags["expense_ratio"],
                "fund_size_aum": bool(aum_val or flags.get("aum")),
                "fund_size_aum_value": aum_val,
                "holdings": flags["holdings"],
                "allocation": flags["allocation"],
                "risk_metrics": risk_present,
                "nav": flags["nav"],
                "holdings_data_present": flags["holdings"],
                "allocation_data_present": flags["allocation"],
                "expense_ratio_present": flags["expense_ratio"],
                "nav_present": flags["nav"],
                "latest_date_found": latest,
                "chunk_count": len(sch_chunks),
            }
        )
    return {
        "total_chunks": len(chunks),
        "funds": funds,
        "funds_with_holdings": sum(1 for f in funds if f["holdings_data_present"]),
        "funds_with_expense_ratio": sum(1 for f in funds if f["expense_ratio_present"]),
    }


def build_freshness_report(
    base_dir: Path, *, stale_nav_days: int = STALE_NAV_FAIL_DAYS
) -> Dict[str, Any]:
    """Summarize manifest, Chroma mtime, and NAV dates found in chunked corpus."""
    base = Path(base_dir).resolve()
    manifest = load_manifest(base) or {}
    chunks, chunk_count = load_chunked_file(base)
    fetch_manifest = load_fetch_manifest(base)
    nav_dates: Set[date] = set()
    nav_date_sources: List[str] = []
    if chunks:
        nav_dates |= collect_nav_dates_from_chunks(chunks)
        if nav_dates:
            nav_date_sources.append("chunks")
    if fetch_manifest:
        fm_dates = collect_nav_dates_from_fetch_manifest(fetch_manifest)
        if fm_dates:
            nav_dates |= fm_dates
            nav_date_sources.append("fetch_manifest")
    nav_max_combined, combined_sources = compute_nav_as_of_max(chunks, fetch_manifest)
    if combined_sources:
        nav_date_sources = combined_sources
    idx = base / "data" / "indexed" / "chroma.sqlite3"

    chroma_mtime: Optional[str] = None
    chroma_size: Optional[int] = None
    if idx.is_file():
        st = idx.stat()
        chroma_mtime = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        chroma_size = st.st_size

    nav_sorted = sorted(nav_dates)
    nav_max = nav_sorted[-1] if nav_sorted else None
    nav_min = nav_sorted[0] if nav_sorted else None
    today = datetime.now(timezone.utc).date()
    nav_stale = False
    nav_age_days: Optional[int] = None
    if nav_max:
        nav_age_days = (today - nav_max).days
        nav_stale = nav_age_days > stale_nav_days

    emb = manifest.get("embedding_model")
    emb_mismatch = bool(emb and emb != _EXPECTED_EMBEDDING)

    return {
        "manifest_last_updated": manifest.get("last_updated"),
        "manifest_source": manifest.get("source"),
        "manifest_embedding_model": emb,
        "embedding_model_mismatch": emb_mismatch,
        "expected_embedding_model": _EXPECTED_EMBEDDING,
        "chunks_total_manifest": manifest.get("chunks_total"),
        "chunks_total_file": chunk_count,
        "chroma_sqlite_mtime_utc": chroma_mtime,
        "chroma_sqlite_size_bytes": chroma_size,
        "nav_dates_found": [d.isoformat() for d in nav_sorted],
        "nav_as_of_min": nav_min.isoformat() if nav_min else None,
        "nav_as_of_max": nav_max.isoformat() if nav_max else None,
        "nav_age_days": nav_age_days,
        "nav_stale_warning": nav_stale,
        "stale_nav_threshold_days": stale_nav_days,
        "nav_date_sources": nav_date_sources,
        "nav_as_of_max_combined": nav_max_combined.isoformat() if nav_max_combined else None,
    }
