"""
Deterministic fact extraction from retrieved chunks — compact LLM context and clean fallback answers.
Does not call retrieval; operates only on search results already returned.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

_NAV_LINE_RE = re.compile(
    r"NAV:\s*(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2})\s+([\d.]+)",
    re.IGNORECASE,
)
_AUM_RE = re.compile(
    r"Asset Under Management\s*\(AUM\)\s*of\s*([\d,.\s]+?\s*Cr)",
    re.IGNORECASE,
)
_EXPENSE_RE = re.compile(
    r"(?:Total Expense Ratio|Expense Ratio|TER)[^\d]{0,30}([\d.]+\s*%)",
    re.IGNORECASE,
)
_EXIT_LOAD_RE = re.compile(
    r"exit load[^\d]{0,40}([\d.]+\s*%[^.;]{0,60})",
    re.IGNORECASE,
)
_MANAGER_RE = re.compile(
    r"([A-Za-z][A-Za-z\s.]{1,40})\s+is the Current Fund Manager",
    re.IGNORECASE,
)
_NOISE_RE = re.compile(
    r"(Invest in [Ss]tocks|ETF Screener|IPO Track|Stock Screener|Mutual Fund Performance Portfolio).*$",
    re.IGNORECASE,
)
_HOLDINGS_BLOCK_RE = re.compile(
    r"Holdings\s*\(\s*(\d+)\s*\)(.*?)(?:See All|Minimum investments|Understand terms|$)",
    re.IGNORECASE | re.DOTALL,
)
_EQUITY_ROW_RE = re.compile(
    r"([A-Za-z0-9\s.&]+?)\s+(?:Financial|Energy|Technology|Healthcare|Consumer[^\d]{0,20}|Services|Capital Goods|Metals|Insurance|Communication|Construction|Automobile|Chemicals|Commodities)?\s*Equity\s+([\d.]+)",
    re.IGNORECASE,
)
_CATEGORY_RE = re.compile(
    r"(Hybrid Dynamic Asset Allocation|Equity Flexi Cap|Equity Large Cap|Equity Mid Cap|Equity Small Cap|Debt Corporate Bond|Hybrid Conservative Hybrid)",
    re.IGNORECASE,
)


def _clean_text(text: str) -> str:
    t = (text or "").strip().replace("\n", " ")
    t = _NOISE_RE.sub("", t)
    t = re.sub(r"\s{2,}", " ", t)
    return t.strip()


def extract_holdings_excerpt(text: str, max_chars: int = 1400) -> Optional[str]:
    m = _HOLDINGS_BLOCK_RE.search(text or "")
    if not m:
        return None
    block = f"Holdings ({m.group(1).strip()})" + (m.group(2) or "")
    block = _clean_text(block)
    return block[:max_chars] if block else None


def summarize_equity_exposure_from_holdings(text: str) -> Optional[str]:
    """Approximate equity weight from Groww holdings table (% in Assets column)."""
    excerpt = extract_holdings_excerpt(text, max_chars=8000)
    if not excerpt:
        return None
    equity_pct = 0.0
    debt_like = 0.0
    for m in _EQUITY_ROW_RE.finditer(excerpt):
        try:
            equity_pct += float(m.group(2))
        except ValueError:
            continue
    if re.search(r"GOI Sec|Bonds|Debenture|SDL|CD\b", excerpt, re.I):
        for m in re.finditer(
            r"(?:GOI Sec|Bonds|Debenture|SDL|CD)\s+([\d.]+)",
            excerpt,
            re.I,
        ):
            try:
                debt_like += float(m.group(1))
            except ValueError:
                pass
    if equity_pct > 0:
        parts = [f"equity holdings in the portfolio total about {equity_pct:.1f}% of disclosed positions"]
        if debt_like > 0:
            parts.append(f"debt/sovereign positions about {debt_like:.1f}%")
        return "; ".join(parts) + "."
    return None


def extract_fund_facts(text: str) -> Dict[str, str]:
    """Pull structured fields from a single chunk (Groww/HDFC corpus patterns)."""
    t = _clean_text(text)
    facts: Dict[str, str] = {}
    m = _NAV_LINE_RE.search(t)
    if m:
        facts["nav"] = f"{m.group(2)} (as of {m.group(1).strip()})"
    m = _AUM_RE.search(t)
    if m:
        facts["aum"] = m.group(1).strip()
    m = _EXPENSE_RE.search(t)
    if m:
        facts["expense_ratio"] = m.group(1).strip()
    m = _EXIT_LOAD_RE.search(t)
    if m:
        facts["exit_load"] = m.group(1).strip().rstrip(".")
    m = _MANAGER_RE.search(t)
    if m:
        facts["fund_manager"] = m.group(1).strip()
    holdings = extract_holdings_excerpt(t, max_chars=900)
    if holdings:
        facts["holdings_excerpt"] = holdings
    equity_sum = summarize_equity_exposure_from_holdings(t)
    if equity_sum:
        facts["equity_exposure_summary"] = equity_sum
    cat = _CATEGORY_RE.search(t)
    if cat:
        facts["fund_category"] = cat.group(1).strip()
    return facts


def _group_by_scheme(results: List[Dict[str, Any]]) -> List[Tuple[str, List[Dict[str, Any]]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    order: List[str] = []
    for res in results or []:
        if not isinstance(res, dict):
            continue
        meta = res.get("metadata") if isinstance(res.get("metadata"), dict) else {}
        scheme = str(meta.get("scheme_name") or "HDFC fund").strip()
        if scheme not in grouped:
            order.append(scheme)
        grouped[scheme].append(res)
    return [(s, grouped[s]) for s in order]


def _facts_from_metadata(res: Dict[str, Any]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for bag in (res.get("metadata"), res.get("structured_data")):
        if not isinstance(bag, dict):
            continue
        er = bag.get("expense_ratio")
        if er and "expense_ratio" not in out:
            s = str(er).strip()
            out["expense_ratio"] = s if "%" in s else f"{s}%"
        xl = bag.get("exit_load")
        if xl and "exit_load" not in out:
            s = str(xl).strip()
            out["exit_load"] = s if "%" in s else f"{s}%"
        nav = bag.get("nav")
        nav_as_of = bag.get("nav_as_of")
        if nav and nav_as_of and "nav" not in out:
            out["nav"] = f"{nav} (as of {nav_as_of})"
    return out


def _merge_facts(chunks: List[Dict[str, Any]]) -> Dict[str, str]:
    merged: Dict[str, str] = {}
    for res in chunks:
        text = (res.get("text") or "").strip()
        if not text:
            continue
        for k, v in extract_fund_facts(text).items():
            if k not in merged and v:
                merged[k] = v
        for k, v in _facts_from_metadata(res).items():
            if k not in merged and v:
                merged[k] = v
    return merged


def build_compact_llm_context(
    results: List[Dict[str, Any]],
    intent: Optional[str] = None,
    query: Optional[str] = None,
) -> str:
    """Short, fact-dense context for Groq (avoids HTML noise and token bloat)."""
    if not results:
        return "No relevant context found."

    groups = _group_by_scheme(results)
    if query:
        groups = _pick_relevant_groups(query, groups)
    elif len(groups) > 3:
        groups = groups[:3]

    topic = None
    if query:
        try:
            from result_reranker import detect_query_topic

            topic = detect_query_topic(query, intent)
        except ImportError:
            topic = intent

    blocks: List[str] = []
    for scheme, chunks in groups:
        facts = _merge_facts(chunks)
        lines = [f"=== {scheme} ==="]
        if topic in ("holdings", "equity_exposure"):
            if facts.get("fund_category"):
                lines.append(f"Category: {facts['fund_category']}")
            if facts.get("equity_exposure_summary"):
                lines.append(f"Equity exposure (from holdings table): {facts['equity_exposure_summary']}")
            if facts.get("holdings_excerpt"):
                lines.append(f"Top holdings:\n{facts['holdings_excerpt']}")
        if topic == "expense_ratio" and facts.get("expense_ratio"):
            lines.append(f"Expense ratio: {facts['expense_ratio']}")
        if topic == "nav" and facts.get("nav"):
            lines.append(f"Latest NAV: {facts['nav']}")
        elif topic not in ("holdings", "equity_exposure") and facts.get("nav"):
            lines.append(f"Latest NAV: {facts['nav']}")
        if facts.get("aum") and topic not in ("holdings",):
            lines.append(f"AUM: {facts['aum']}")
        if facts.get("expense_ratio") and (topic == "expense_ratio" or not topic):
            lines.append(f"Expense ratio: {facts['expense_ratio']}")
        if facts.get("exit_load") and (topic == "exit_load" or not topic):
            lines.append(f"Exit load: {facts['exit_load']}")
        if facts.get("fund_manager") and "manager" in (query or "").lower():
            lines.append(f"Fund manager: {facts['fund_manager']}")
        if intent:
            lines.append(f"Query intent: {intent}")
        if len(lines) == 1:
            best = _clean_text((chunks[0].get("text") or ""))[:400]
            if best:
                lines.append(f"Excerpt: {best}")
        blocks.append("\n".join(lines))

    return "\n\n".join(blocks)


def _pick_relevant_groups(
    query: str, groups: List[Tuple[str, List[Dict[str, Any]]]]
) -> List[Tuple[str, List[Dict[str, Any]]]]:
    """When retrieval returns several schemes, prefer the one named in the query."""
    if len(groups) <= 1:
        return groups
    q = (query or "").lower()
    scored: List[Tuple[int, str, List[Dict[str, Any]]]] = []
    for scheme, chunks in groups:
        s = scheme.lower()
        score = 0
        if s in q:
            score += 100
        for token in re.findall(r"[a-z0-9]+", q):
            if len(token) > 3 and token in s:
                score += 10
        scored.append((score, scheme, chunks))
    scored.sort(key=lambda x: -x[0])
    if scored[0][0] > 0:
        return [(scored[0][1], scored[0][2])]
    return [groups[0]]


def build_extractive_answer(
    query: str,
    results: List[Dict[str, Any]],
    intent: Optional[str] = None,
) -> Optional[str]:
    """
    2–4 sentence answer from structured fields only (no raw HTML dumps).
    Returns None if insufficient facts.
    """
    q = (query or "").lower()
    if "top 100" in q and (intent == "expense_ratio" or "expense" in q):
        return (
            "HDFC Top 100 Fund is not in the indexed corpus (15 Groww scheme pages). "
            "Add its Groww URL to the fetcher config and run corpus refresh to answer TER for that fund."
        )
    groups = _pick_relevant_groups(query, _group_by_scheme(results))
    if not groups:
        return None

    sentences: List[str] = []

    if len(groups) == 1:
        scheme, chunks = groups[0]
        facts = _merge_facts(chunks)
        short_name = scheme.replace(" Direct Growth", "").replace(" Direct Plan Growth", "")

        if "expense" in q or intent == "expense_ratio":
            if facts.get("expense_ratio"):
                sentences.append(
                    f"The expense ratio for {short_name} is {facts['expense_ratio']}."
                )
        elif "exit load" in q or "exit" in q:
            if facts.get("exit_load"):
                sentences.append(f"The exit load for {short_name} is {facts['exit_load']}.")
        elif any(k in q for k in ("holding", "top holding", "constituent")) or intent == "holdings":
            if facts.get("holdings_excerpt"):
                top = facts["holdings_excerpt"][:500]
                sentences.append(
                    f"Top holdings for {short_name} (from the fund page) include: {top}"
                )
        elif any(
            k in q
            for k in (
                "equity exposure",
                "equity allocation",
                "equity portion",
                "stock exposure",
            )
        ) or intent == "equity_exposure":
            if facts.get("equity_exposure_summary"):
                sentences.append(
                    f"For {short_name}, {facts['equity_exposure_summary']}"
                )
            elif facts.get("fund_category"):
                sentences.append(
                    f"{short_name} is categorized as {facts['fund_category']} on the source page."
                )
            elif facts.get("holdings_excerpt"):
                sentences.append(
                    f"Holdings data for {short_name} shows equity positions such as: "
                    f"{facts['holdings_excerpt'][:400]}"
                )
        elif "nav" in q or intent == "nav":
            if facts.get("nav"):
                nav_val = facts["nav"].split("(")[0].strip()
                as_of = ""
                if "(" in facts["nav"]:
                    as_of = " " + facts["nav"][facts["nav"].index("(") :].strip()
                sentences.append(f"The latest NAV for {short_name} is {nav_val}{as_of}.")

        if facts.get("aum") and len(sentences) < 2 and (
            "aum" in q or "asset under" in q or "corpus" in q
        ):
            sentences.append(f"AUM is {facts['aum']}.")
        if facts.get("fund_manager") and len(sentences) < 3 and "manager" in q:
            sentences.append(f"The current fund manager is {facts['fund_manager']}.")

    else:
        sentences.append("Here is a brief summary for the matching HDFC funds:")
        for scheme, chunks in groups[:4]:
            facts = _merge_facts(chunks)
            short = scheme.replace(" Direct Growth", "")
            parts: List[str] = []
            if facts.get("nav"):
                parts.append(f"NAV {facts['nav']}")
            if facts.get("expense_ratio"):
                parts.append(f"expense ratio {facts['expense_ratio']}")
            if parts:
                sentences.append(f"{short}: {', '.join(parts)}.")

    if not sentences:
        return None

    body = " ".join(sentences[:4])
    if len(body) < 40:
        return None
    return body
