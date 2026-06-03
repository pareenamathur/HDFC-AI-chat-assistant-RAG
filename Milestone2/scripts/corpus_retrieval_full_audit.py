#!/usr/bin/env python3
"""
Evidence-based corpus + retrieval audit (read-only on infrastructure).
Writes reports/corpus_retrieval_audit.json and prints summary tables.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "phase2_retrieval_layer" / "src"))
sys.path.insert(0, str(ROOT / "phase3_reasoning_guardrails" / "src"))
sys.path.insert(0, str(ROOT / "backend"))

from corpus_diagnostics import (  # noqa: E402
    collect_nav_dates_from_chunks,
    parse_nav_token,
    parse_iso_nav_date,
)

CHUNKED = ROOT / "data" / "processed" / "chunked_data_phase1.4.json"
MANIFEST = ROOT / "data" / "fetch_manifest.json"
INDEXED = ROOT / "data" / "indexed"
REPORT_DIR = ROOT / "reports"

TEST_QUERIES = [
    "What is the equity exposure in HDFC Balanced Advantage Fund?",
    "What are the top holdings of HDFC Flexi Cap Fund?",
    "What is the expense ratio of HDFC Top 100 Fund?",
]

_NAV_RE = re.compile(r"NAV:\s*\d", re.I)
_HOLDINGS_RE = re.compile(r"Holdings\s*\(\s*\d+\s*\)", re.I)
_EXPENSE_RE = re.compile(r"(?:Total Expense Ratio|Expense Ratio|TER)\s*[^\d]{0,20}([\d.]+\s*%)", re.I)
_ALLOC_RE = re.compile(
    r"(?:asset allocation|allocation|equity\s*:\s*|debt\s*:\s*|hybrid dynamic)",
    re.I,
)
_RISK_RE = re.compile(r"(?:riskometer|risk level|very high|moderately high|low to moderate)", re.I)
_BOILERPLATE_RE = re.compile(
    r"invest in stocks|etf screener|stock screener|mutual fund performance portfolio",
    re.I,
)


def classify_chunk(text: str) -> Set[str]:
    tags: Set[str] = set()
    t = text or ""
    if _NAV_RE.search(t):
        tags.add("nav")
    if _HOLDINGS_RE.search(t):
        tags.add("holdings")
    if _EXPENSE_RE.search(t):
        tags.add("expense_ratio")
    if _ALLOC_RE.search(t):
        tags.add("allocation")
    if _RISK_RE.search(t):
        tags.add("risk")
    if _BOILERPLATE_RE.search(t[:500]):
        tags.add("boilerplate")
    if not tags:
        tags.add("other")
    return tags


def chunk_nav_date(text: str, meta: dict) -> Optional[str]:
    for m in re.finditer(r"NAV:\s*(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2})", text or "", re.I):
        d = parse_nav_token(m.group(0))
        if d:
            return d.isoformat()
    if isinstance(meta, dict):
        d = parse_iso_nav_date(meta.get("nav_as_of"))
        if d:
            return d.isoformat()
    return None


def normalize_scheme(name: str) -> str:
    return (name or "?").replace(" Direct Growth", "").replace(" Direct Plan Growth", "").strip()


def load_chunks() -> List[Dict[str, Any]]:
    with open(CHUNKED, encoding="utf-8") as f:
        return json.load(f)


def source_audit(chunks: List[Dict[str, Any]], fetch: Optional[Dict]) -> List[Dict[str, Any]]:
    by_url: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for c in chunks:
        meta = c.get("metadata") or {}
        url = meta.get("source_url") or meta.get("url") or "unknown"
        by_url[str(url)].append(c)

    entries = {e.get("url"): e for e in (fetch or {}).get("entries") or [] if e.get("url")}
    rows: List[Dict[str, Any]] = []
    for url, url_chunks in sorted(by_url.items()):
        types: Counter = Counter()
        dates: List[str] = []
        for c in url_chunks:
            text = c.get("text") or ""
            for tag in classify_chunk(text):
                types[tag] += 1
            nd = chunk_nav_date(text, c.get("metadata") or {})
            if nd:
                dates.append(nd)
        fe = entries.get(url) or {}
        rows.append(
            {
                "source_url": url,
                "scheme_name": (url_chunks[0].get("metadata") or {}).get("scheme_name"),
                "chunk_count": len(url_chunks),
                "content_types_in_chunks": dict(types),
                "latest_nav_date_in_chunks": max(dates) if dates else None,
                "fetch_nav_as_of": fe.get("nav_as_of"),
                "fetch_fetched_at": fe.get("fetched_at"),
                "html_file": fe.get("html_file"),
            }
        )
    return rows


def coverage_report(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_scheme: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for c in chunks:
        sn = c.get("scheme_name") or (c.get("metadata") or {}).get("scheme_name") or "?"
        by_scheme[sn].append(c)

    rows = []
    for scheme, sch_chunks in sorted(by_scheme.items()):
        flags = {
            "holdings": False,
            "allocation": False,
            "expense_ratio": False,
            "nav": False,
            "risk": False,
        }
        latest: Optional[str] = None
        for c in sch_chunks:
            text = c.get("text") or ""
            tags = classify_chunk(text)
            for k in flags:
                if k in tags:
                    flags[k] = True
            nd = chunk_nav_date(text, c.get("metadata") or {})
            if nd and (latest is None or nd > latest):
                latest = nd
        rows.append(
            {
                "fund_name": normalize_scheme(scheme),
                "scheme_name_full": scheme,
                "holdings_data_present": flags["holdings"],
                "allocation_data_present": flags["allocation"],
                "expense_ratio_present": flags["expense_ratio"],
                "nav_present": flags["nav"],
                "risk_present": flags["risk"],
                "latest_date_found": latest,
                "chunk_count": len(sch_chunks),
            }
        )
    return rows


def chunk_analysis(chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
    text_hashes: Counter = Counter()
    prefix_hashes: Counter = Counter()
    nav_dom = 0
    holdings_dom = 0
    tag_counts: Counter = Counter()
    for c in chunks:
        text = c.get("text") or ""
        h = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]
        text_hashes[h] += 1
        prefix_hashes[(text[:200] or "").strip()] += 1
        tags = classify_chunk(text)
        if "nav" in tags and len(tags) == 1:
            nav_dom += 1
        if "holdings" in tags:
            holdings_dom += 1
        for t in tags:
            tag_counts[t] += 1
    exact_dupes = sum(1 for _, n in text_hashes.items() if n > 1)
    prefix_dupes = sum(1 for _, n in prefix_hashes.items() if n > 1)
    nav_only_pct = round(100.0 * nav_dom / max(len(chunks), 1), 1)
    return {
        "total_chunks": len(chunks),
        "exact_duplicate_hash_groups": exact_dupes,
        "duplicate_chunks_from_exact_hash": sum(n - 1 for n in text_hashes.values() if n > 1),
        "repetitive_prefix_groups": prefix_dupes,
        "chunks_tagged_nav_only": nav_dom,
        "nav_only_percentage": nav_only_pct,
        "chunks_with_holdings_tag": holdings_dom,
        "tag_counts_across_chunks": dict(tag_counts),
        "boilerplate_tagged_chunks": tag_counts.get("boilerplate", 0),
    }


def retrieval_audit(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    from query_processor import QueryProcessor  # noqa: E402
    from retriever import HybridRetriever  # noqa: E402
    from result_reranker import boost_results_for_query  # noqa: E402
    from extractive_fallback import build_compact_llm_context, build_extractive_answer  # noqa: E402

    schemes = sorted(
        {c.get("scheme_name") or (c.get("metadata") or {}).get("scheme_name") for c in chunks}
        - {None}
    )
    qp = QueryProcessor([s for s in schemes if s])
    retriever = HybridRetriever(
        persist_directory=str(INDEXED),
        use_bm25=False,
        use_reranker=False,
        vector_fetch_k=12,
    )

    out = []
    for query in TEST_QUERIES:
        proc = qp.process_query(query)
        filters = proc["filters"] or None
        if filters == {}:
            filters = None
        n = 12 if proc["intent"] in ("holdings", "equity_exposure", "expense_ratio") else 8
        results = retriever.search(query, n_results=n, filters=filters)
        filtered_empty = not results and bool(filters)
        if filtered_empty:
            results = retriever.search(query, n_results=n, filters=None)
        boosted = boost_results_for_query(query, results, intent=proc["intent"])
        scheme = (filters or {}).get("scheme_name") if isinstance(filters, dict) else None
        topic = proc["intent"]
        if scheme and topic in ("holdings", "equity_exposure"):
            extra = retriever.fetch_chunks_matching_text(scheme, "Holdings (", limit=3)
            seen = {r.get("id") for r in boosted}
            boosted = extra + [r for r in boosted if r.get("id") not in seen]
        elif scheme and topic == "expense_ratio":
            extra = retriever.fetch_chunks_matching_text(scheme, "Total Expense Ratio", limit=3)
            if not extra:
                extra = retriever.fetch_chunks_matching_text(scheme, "Scheme facts for", limit=2)
            seen = {r.get("id") for r in boosted}
            boosted = extra + [r for r in boosted if r.get("id") not in seen]
        hits = []
        for i, r in enumerate(boosted[:10], 1):
            meta = r.get("metadata") or {}
            text = r.get("text") or ""
            hits.append(
                {
                    "rank": i,
                    "score": round(float(r.get("score") or 0), 4),
                    "score_adjusted": round(float(r.get("score_adjusted") or r.get("score") or 0), 4),
                    "chunk_id": r.get("id"),
                    "scheme_name": meta.get("scheme_name"),
                    "source_url": meta.get("source_url"),
                    "has_holdings_table": bool(_HOLDINGS_RE.search(text)),
                    "has_nav_line": bool(_NAV_RE.search(text)),
                    "has_expense_ratio": bool(_EXPENSE_RE.search(text)),
                    "preview": text.replace("\n", " ")[:180],
                }
            )
        out.append(
            {
                "query": query,
                "filters": proc["filters"],
                "intent": proc["intent"],
                "retrieval_used_filter": filters is not None,
                "retried_without_filter": filtered_empty,
                "top_hits": hits,
                "compact_llm_context": build_compact_llm_context(
                    boosted, intent=proc["intent"], query=query
                )[:1500],
                "extractive_answer": build_extractive_answer(
                    query, boosted, intent=proc["intent"]
                ),
            }
        )
    return out


def root_cause_hints(
    sources: List[Dict],
    coverage: List[Dict],
    chunk_stats: Dict,
    retrieval: List[Dict],
) -> List[str]:
    hints: List[str] = []
    if chunk_stats.get("nav_only_percentage", 0) > 40:
        hints.append(
            f"CORPUS: {chunk_stats['nav_only_percentage']}% of chunks are NAV-only tagged — vector search may cluster on NAV boilerplate."
        )
    if chunk_stats.get("duplicate_chunks_from_exact_hash", 0) > 20:
        hints.append(
            f"CORPUS: {chunk_stats['duplicate_chunks_from_exact_hash']} near-duplicate chunks inflate repeated NAV answers."
        )
    top100 = [c for c in coverage if "top 100" in c["fund_name"].lower()]
    if not top100:
        hints.append(
            "COVERAGE: HDFC Top 100 Fund is NOT in the indexed corpus (15 Groww URLs only) — expense-ratio query cannot be fund-specific."
        )
    for row in retrieval:
        q = row["query"]
        hits = row["top_hits"]
        if not hits:
            hints.append(f"RETRIEVAL: zero hits for {q!r}")
            continue
        top = hits[0]
        if "equity" in q.lower() or "holding" in q.lower():
            if not top.get("has_holdings_table") and top.get("has_nav_line"):
                hints.append(
                    f"RETRIEVAL: {q[:50]}… — rank-1 is NAV chunk (score {top['score']}), not holdings."
                )
        if "expense" in q.lower():
            if not top.get("has_expense_ratio"):
                hints.append(
                    f"RETRIEVAL: expense query rank-1 lacks TER in text — wrong scheme or missing content."
                )
        ctx = row.get("compact_llm_context") or ""
        if "Latest NAV" in ctx and "equity" in q.lower() and "Equity exposure" not in ctx:
            hints.append(
                f"CONTEXT: compact LLM context for equity/holdings query still leads with NAV — explains similar LLM answers."
            )
    stale = [
        c
        for c in coverage
        if c.get("latest_date_found") and c["latest_date_found"] < "2026-06-01"
    ]
    if stale:
        hints.append(
            f"FRESHNESS: {len(stale)} schemes have chunk NAV dates before 2026-06-01 in text (inline stale NAV lines)."
        )
    return hints


def print_coverage_table(coverage: List[Dict]) -> None:
    print("\n## Corpus Coverage Report\n")
    print(
        "| Fund Name | Holdings | Allocation | Expense Ratio | NAV | Latest Date | Chunks |"
    )
    print("| --- | --- | --- | --- | --- | --- | --- |")
    for r in coverage:
        yn = lambda b: "Yes" if b else "No"
        print(
            f"| {r['fund_name']} | {yn(r['holdings_data_present'])} | "
            f"{yn(r['allocation_data_present'])} | {yn(r['expense_ratio_present'])} | "
            f"{yn(r['nav_present'])} | {r['latest_date_found'] or '—'} | {r['chunk_count']} |"
        )


def main() -> int:
    if not CHUNKED.is_file():
        print("Missing", CHUNKED)
        return 1
    chunks = load_chunks()
    fetch = None
    if MANIFEST.is_file():
        with open(MANIFEST, encoding="utf-8") as f:
            fetch = json.load(f)

    sources = source_audit(chunks, fetch)
    coverage = coverage_report(chunks)
    chunk_stats = chunk_analysis(chunks)
    nav_dates = sorted(collect_nav_dates_from_chunks(chunks))

    retrieval = []
    chroma_ok = (INDEXED / "chroma.sqlite3").is_file()
    if chroma_ok:
        retrieval = retrieval_audit(chunks)
    else:
        print("WARN: no chroma.sqlite3 — skipping live retrieval audit")

    hints = root_cause_hints(sources, coverage, chunk_stats, retrieval)

    report = {
        "generated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "chunk_file": str(CHUNKED),
        "total_chunks": len(chunks),
        "nav_dates_in_corpus": [d.isoformat() for d in nav_dates],
        "nav_as_of_max": nav_dates[-1].isoformat() if nav_dates else None,
        "source_audit": sources,
        "coverage_report": coverage,
        "chunk_analysis": chunk_stats,
        "retrieval_audit": retrieval,
        "root_cause_hints": hints,
    }

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REPORT_DIR / "corpus_retrieval_audit.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print("Wrote", out_path)

    print("\n## Source URLs (indexed)\n")
    for s in sources:
        print(f"- {s['source_url']}")
        print(
            f"  chunks={s['chunk_count']} types={s['content_types_in_chunks']} "
            f"latest_nav_in_chunks={s['latest_nav_date_in_chunks']} fetch_nav={s['fetch_nav_as_of']}"
        )

    print_coverage_table(coverage)

    print("\n## Chunk Analysis\n", json.dumps(chunk_stats, indent=2))

    if retrieval:
        print("\n## Retrieval Audit\n")
        for block in retrieval:
            print(f"\n### {block['query']}\n")
            print(f"filters={block['filters']} intent={block['intent']}")
            for h in block["top_hits"]:
                print(
                    f"  {h['rank']}. score={h['score']} adj={h['score_adjusted']} "
                    f"holdings={h['has_holdings_table']} nav={h['has_nav_line']} ter={h['has_expense_ratio']}"
                )
                print(f"     {h['scheme_name']}")
                print(f"     {h['preview'][:120]}…")
            print(f"\nextractive: {block['extractive_answer']!r}")
            print(f"\ncompact context (excerpt):\n{block['compact_llm_context'][:600]}")

    print("\n## Root Cause Hints (evidence-based)\n")
    for h in hints:
        print(f"- {h}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
