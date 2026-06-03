"""
Query-aware reranking on top of vector scores — surfaces holdings / allocation chunks.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

_GROWW_NOISE = re.compile(
    r"invest in stocks|etf screener|stock screener|mutual fund performance portfolio",
    re.I,
)
_HOLDINGS_MARK = re.compile(r"Holdings\s*\(\s*\d+\s*\)", re.I)


def detect_query_topic(query: str, intent: Optional[str] = None) -> Optional[str]:
    if intent == "nav":
        return "nav"
    if intent == "holdings":
        return "holdings"
    if intent == "equity_exposure":
        return "equity_exposure"
    if intent == "expense_ratio":
        return "expense_ratio"
    if intent == "aum":
        return "aum"
    q = (query or "").lower()
    if any(k in q for k in ("holding", "top holding", "constituent", "portfolio holding")):
        return "holdings"
    if any(
        k in q
        for k in (
            "equity exposure",
            "equity allocation",
            "equity portion",
            "stock exposure",
            "how much equity",
            "equity weight",
        )
    ):
        return "equity_exposure"
    if any(k in q for k in ("fund size", "aum", "asset under management")):
        return "aum"
    if any(k in q for k in ("expense ratio", "expense", "ter")):
        return "expense_ratio"
    if "nav" in q and not any(k in q for k in ("holding", "exposure", "allocation")):
        return "nav"
    return None


def _topic_boost(text: str, topic: Optional[str]) -> float:
    if not topic:
        return 0.0
    t = text or ""
    boost = 0.0
    if topic == "holdings" and _HOLDINGS_MARK.search(t):
        boost += 0.35
    if topic == "equity_exposure":
        if _HOLDINGS_MARK.search(t):
            boost += 0.28
        if re.search(r"hybrid dynamic asset allocation|equity savings|multi asset", t, re.I):
            boost += 0.12
        if re.search(r"instruments\s+equity\s+\d", t, re.I):
            boost += 0.15
    if topic == "aum":
        if re.search(r"Fund size\s*\(AUM\)|Scheme facts for", t, re.I):
            boost += 0.32
    if topic == "expense_ratio":
        if re.search(r"Total Expense Ratio|Expense Ratio|TER:", t, re.I):
            boost += 0.38
        if re.search(r"expense_ratio\s+[\d.]", t, re.I):
            boost += 0.22
        if t.startswith("Scheme facts for"):
            boost += 0.25
    if topic == "nav" and re.search(r"\|\s*NAV:\s*\d", t, re.I):
        boost += 0.08
    if _GROWW_NOISE.search(t[:400]) and not _HOLDINGS_MARK.search(t):
        boost -= 0.12
    return boost


def boost_results_for_query(
    query: str,
    results: List[Dict[str, Any]],
    *,
    intent: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Re-sort by vector score + topic relevance (stable tie-break on id)."""
    if not results:
        return results
    topic = detect_query_topic(query, intent)
    if not topic:
        return results

    scored: List[tuple[float, str, Dict[str, Any]]] = []
    for r in results:
        base = float(r.get("score") or 0.0)
        text = r.get("text") or ""
        combined = base + _topic_boost(text, topic)
        scored.append((combined, str(r.get("id") or ""), r))

    scored.sort(key=lambda x: (-x[0], x[1]))
    out: List[Dict[str, Any]] = []
    for combined, _, r in scored:
        row = dict(r)
        row["rerank_topic"] = topic
        row["score_adjusted"] = combined
        out.append(row)
    return out
