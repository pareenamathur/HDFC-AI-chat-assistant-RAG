#!/usr/bin/env python3
"""Evidence-based RAG pipeline audit — retrieval, context, corpus stats."""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "phase2_retrieval_layer" / "src"))
sys.path.insert(0, str(ROOT / "phase3_reasoning_guardrails" / "src"))

from query_processor import QueryProcessor  # noqa: E402
from retriever import HybridRetriever  # noqa: E402
from result_reranker import boost_results_for_query  # noqa: E402
from context_builder import ContextBuilder  # noqa: E402
from extractive_fallback import build_compact_llm_context, build_extractive_answer, extract_fund_facts  # noqa: E402

TEST_QUERIES = [
    "What is the equity exposure in HDFC Balanced Advantage Fund?",
    "What are the top holdings of HDFC Flexi Cap Fund?",
    "What is the NAV of HDFC Nifty 50 Index Fund?",
]

CHUNKED = ROOT / "data" / "processed" / "chunked_data_phase1.4.json"
INDEXED = ROOT / "data" / "indexed"


def load_schemes() -> list[str]:
    with open(CHUNKED, encoding="utf-8") as f:
        chunks = json.load(f)
    names = sorted({c.get("scheme_name") or (c.get("metadata") or {}).get("scheme_name") for c in chunks if c})
    return [n for n in names if n]


def corpus_report(chunks: list) -> None:
    print("\n" + "=" * 72)
    print("CORPUS ANALYSIS")
    print("=" * 72)
    by_scheme = Counter()
    nav_leading = 0
    holdings_chunks = 0
    text_hashes = Counter()
    for c in chunks:
        sn = c.get("scheme_name") or (c.get("metadata") or {}).get("scheme_name") or "?"
        by_scheme[sn] += 1
        t = (c.get("text") or "")[:120]
        if re.search(r"NAV:\s*\d", c.get("text") or "", re.I):
            nav_leading += 1
        if re.search(r"Holdings\s*\(\s*\d+", c.get("text") or "", re.I):
            holdings_chunks += 1
        text_hashes[t] += 1
    print("\nFund name | chunk count")
    print("--- | ---")
    for name, cnt in by_scheme.most_common():
        print(f"{name} | {cnt}")
    dupes = sum(1 for _, n in text_hashes.items() if n > 1)
    print(f"\nChunks with NAV pattern in text: {nav_leading}/{len(chunks)}")
    print(f"Chunks with Holdings table: {holdings_chunks}/{len(chunks)}")
    print(f"Duplicate chunk prefixes (same first 120 chars): {dupes} groups")


def audit_query(qp: QueryProcessor, retriever: HybridRetriever, query: str) -> None:
    print("\n" + "=" * 72)
    print(f"QUERY: {query}")
    print("=" * 72)
    proc = qp.process_query(query)
    print(f"process_query -> filters={proc['filters']!r} intent={proc['intent']!r}")
    print(f"normalized_query={proc['normalized_query']!r}")

    filters = proc["filters"] or None
    if filters == {}:
        filters = None

    n = 12 if proc["intent"] in ("holdings", "equity_exposure") else 8
    results = retriever.search(query, n_results=n, filters=filters)
    if not results and filters:
        print("WARN: zero hits with filter — retrying without filter")
        results = retriever.search(query, n_results=n, filters=None)
    results = boost_results_for_query(query, results, intent=proc["intent"])

    print(f"\nTop-{len(results)} retrieved chunks:")
    print("rank | score | chunk_id | scheme | source_url | preview")
    print("--- | --- | --- | --- | --- | ---")
    for i, r in enumerate(results, 1):
        meta = r.get("metadata") or {}
        preview = (r.get("text") or "").replace("\n", " ")[:100]
        has_holdings = "Holdings (" in (r.get("text") or "")
        print(
            f"{i} | {r.get('score', 0):.4f} | {r.get('id', '')[:24]} | "
            f"{meta.get('scheme_name', '')[:40]} | {str(meta.get('source_url', ''))[:50]} | "
            f"{'[HOLDINGS] ' if has_holdings else ''}{preview!r}"
        )

    ctx = ContextBuilder.build_context(results, intent=proc["intent"])
    compact = build_compact_llm_context(results, intent=proc["intent"], query=query)
    extractive = build_extractive_answer(query, results, intent=proc["intent"])

    print(f"\ncompact_llm_context ({len(compact)} chars):\n{compact[:1200]}")
    print(f"\nextractive_answer: {extractive!r}")
    print(f"\nfull_context first 800 chars:\n{ctx[:800]}")


def main() -> int:
    if not CHUNKED.is_file():
        print("Missing chunked data:", CHUNKED)
        return 1
    with open(CHUNKED, encoding="utf-8") as f:
        chunks = json.load(f)

    corpus_report(chunks)
    schemes = load_schemes()
    qp = QueryProcessor(schemes)
    retriever = HybridRetriever(
        persist_directory=str(INDEXED),
        use_bm25=False,
        use_reranker=False,
        vector_fetch_k=12,
    )
    print(f"\nChroma count={retriever.collection.count()} embedding_model={retriever.embedding_model_name}")

    for q in TEST_QUERIES:
        audit_query(qp, retriever, q)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
