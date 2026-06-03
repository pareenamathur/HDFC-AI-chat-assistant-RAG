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
_FUND_SIZE_RE = re.compile(
    r"Fund size\s*\(AUM\)\s*:\s*([^\n]+)",
    re.IGNORECASE,
)
_AMC_WIDE_AUM_SNIPPET = "9,37,048"


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
    m = _FUND_SIZE_RE.search(t)
    if m:
        facts["aum"] = m.group(1).strip()
    else:
        m = _AUM_RE.search(t)
        if m:
            aum_val = m.group(1).strip()
            if _AMC_WIDE_AUM_SNIPPET not in aum_val.replace(" ", ""):
                facts["aum"] = aum_val
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
        aum = bag.get("aum")
        if aum is not None and str(aum).strip() and "aum" not in out:
            out["aum"] = _format_aum_display(aum)
        risk = bag.get("risk_level")
        if risk and "risk_level" not in out:
            out["risk_level"] = str(risk).strip()
    return out


def _format_aum_display(raw: Any) -> str:
    s = str(raw or "").strip().replace(",", "")
    if not s:
        return ""
    if "cr" in s.lower():
        return s
    try:
        v = float(s)
        if v >= 1000:
            return f"{v:,.2f} Cr"
        return f"{v:.2f} Cr"
    except ValueError:
        return s if s.endswith("Cr") else f"{s} Cr"


def detect_requested_attributes(query: str) -> List[str]:
    try:
        from query_processor import QueryProcessor

        return QueryProcessor.detect_requested_attributes(query)
    except ImportError:
        q = (query or "").lower()
        attrs: List[str] = []
        if any(k in q for k in ("expense", "ter")):
            attrs.append("expense_ratio")
        if any(k in q for k in ("fund size", "aum", "asset under")):
            attrs.append("aum")
        return attrs


def is_comparison_query(query: str) -> bool:
    try:
        from query_processor import QueryProcessor

        return QueryProcessor.is_comparison_query(query)
    except ImportError:
        return "compare" in (query or "").lower()


def _filters_list_schemes(filters: Optional[Dict[str, Any]]) -> List[str]:
    if not isinstance(filters, dict):
        return []
    sn = filters.get("scheme_name")
    if isinstance(sn, dict) and "$in" in sn:
        return [str(s) for s in sn["$in"] if s]
    if isinstance(sn, str) and sn:
        return [sn]
    return []


def _merge_facts(chunks: List[Dict[str, Any]]) -> Dict[str, str]:
    merged: Dict[str, str] = {}
    for res in chunks:
        for k, v in _facts_from_metadata(res).items():
            if v and k not in merged:
                merged[k] = v
    for res in chunks:
        text = (res.get("text") or "").strip()
        if not text:
            continue
        for k, v in extract_fund_facts(text).items():
            if k not in merged and v:
                if k == "aum" and _AMC_WIDE_AUM_SNIPPET in v.replace(" ", ""):
                    continue
                merged[k] = v
    return merged


def _pick_relevant_groups(
    query: str,
    groups: List[Tuple[str, List[Dict[str, Any]]]],
    *,
    filters: Optional[Dict[str, Any]] = None,
) -> List[Tuple[str, List[Dict[str, Any]]]]:
    """Keep all schemes for comparisons / multi-fund filters; else best single match."""
    if len(groups) <= 1:
        return groups

    filter_schemes = _filters_list_schemes(filters)
    if is_comparison_query(query) or len(filter_schemes) > 1:
        by_name = {s: c for s, c in groups}
        if filter_schemes:
            picked = [(s, by_name[s]) for s in filter_schemes if s in by_name]
            if picked:
                return picked
        q = (query or "").lower()
        scored: List[Tuple[int, str, List[Dict[str, Any]]]] = []
        for scheme, chunks in groups:
            s = scheme.lower()
            score = 0
            for token in re.findall(r"[a-z0-9]+", q):
                if len(token) > 3 and token in s:
                    score += 10
            if score > 0:
                scored.append((score, scheme, chunks))
        scored.sort(key=lambda x: -x[0])
        if len(scored) >= 2:
            return [(s, c) for _, s, c in scored[:8]]
        if scored:
            return [(scored[0][1], scored[0][2])]

    q = (query or "").lower()
    scored = []
    for scheme, chunks in groups:
        s = scheme.lower()
        score = 100 if s in q else 0
        for token in re.findall(r"[a-z0-9]+", q):
            if len(token) > 3 and token in s:
                score += 10
        scored.append((score, scheme, chunks))
    scored.sort(key=lambda x: -x[0])
    if scored[0][0] > 0:
        return [(scored[0][1], scored[0][2])]
    return [groups[0]]


def _append_fact_lines(
    lines: List[str],
    facts: Dict[str, str],
    requested: List[str],
    query: str,
) -> None:
    q = (query or "").lower()
    want = set(requested) if requested else set()
    if not want:
        if "expense" in q:
            want.add("expense_ratio")
        if any(k in q for k in ("fund size", "aum", "asset under")):
            want.add("aum")
        if "nav" in q:
            want.add("nav")
        if any(k in q for k in ("holding", "constituent")):
            want.add("holdings")
        if "risk" in q:
            want.add("risk_level")

    if "expense_ratio" in want and facts.get("expense_ratio"):
        lines.append(f"Expense ratio: {facts['expense_ratio']}")
    if "aum" in want and facts.get("aum"):
        lines.append(f"Fund size (AUM): {facts['aum']}")
    if "nav" in want and facts.get("nav"):
        lines.append(f"Latest NAV: {facts['nav']}")
    if "risk_level" in want and facts.get("risk_level"):
        lines.append(f"Risk level: {facts['risk_level']}")
    if "holdings" in want and facts.get("holdings_excerpt"):
        lines.append(f"Top holdings:\n{facts['holdings_excerpt']}")
    if "equity_exposure" in want and facts.get("equity_exposure_summary"):
        lines.append(f"Equity exposure: {facts['equity_exposure_summary']}")
    if facts.get("exit_load") and ("exit_load" in want or "exit load" in q):
        lines.append(f"Exit load: {facts['exit_load']}")
    if facts.get("fund_category"):
        lines.append(f"Category: {facts['fund_category']}")


def build_compact_llm_context(
    results: List[Dict[str, Any]],
    intent: Optional[str] = None,
    query: Optional[str] = None,
    filters: Optional[Dict[str, Any]] = None,
    requested_attributes: Optional[List[str]] = None,
) -> str:
    """Short, fact-dense context for Groq (avoids HTML noise and token bloat)."""
    if not results:
        return "No relevant context found."

    groups = _group_by_scheme(results)
    if query:
        groups = _pick_relevant_groups(query, groups, filters=filters)
    elif len(groups) > 3:
        groups = groups[:3]

    requested = requested_attributes or (detect_requested_attributes(query or "") if query else [])
    blocks: List[str] = []
    for scheme, chunks in groups:
        facts = _merge_facts(chunks)
        lines = [f"=== {scheme} ==="]
        _append_fact_lines(lines, facts, requested, query or "")
        if intent:
            lines.append(f"Query intent: {intent}")
        if len(lines) == 1:
            best = _clean_text((chunks[0].get("text") or ""))[:400]
            if best:
                lines.append(f"Excerpt: {best}")
        blocks.append("\n".join(lines))

    return "\n\n".join(blocks)


def log_attribute_diagnostics(
    logger: Any,
    query: str,
    results: List[Dict[str, Any]],
    *,
    requested_attributes: Optional[List[str]] = None,
    filters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Log retrieved chunks vs extracted vs missing attributes per scheme."""
    requested = requested_attributes or detect_requested_attributes(query)
    groups = _pick_relevant_groups(query, _group_by_scheme(results), filters=filters)
    report: Dict[str, Any] = {
        "requested_attributes": requested,
        "schemes": [],
    }
    for scheme, chunks in groups:
        facts = _merge_facts(chunks)
        missing = [a for a in requested if not facts.get(a)]
        entry = {
            "scheme": scheme,
            "chunk_count": len(chunks),
            "extracted": {k: facts[k] for k in facts if k in requested or k in facts},
            "missing_requested": missing,
            "top_chunk_previews": [
                (c.get("text") or "").replace("\n", " ")[:100] for c in chunks[:3]
            ],
        }
        report["schemes"].append(entry)
        logger.info(
            "attribute_diag scheme=%r chunks=%s extracted_keys=%s missing=%s",
            scheme,
            len(chunks),
            list(facts.keys()),
            missing,
        )
    return report


def _short_scheme_name(scheme: str) -> str:
    return (
        scheme.replace(" Direct Growth", "")
        .replace(" Direct Plan Growth", "")
        .strip()
    )


def _build_single_fund_sentences(
    short_name: str,
    facts: Dict[str, str],
    requested: List[str],
    query: str,
) -> List[str]:
    sentences: List[str] = []
    q = (query or "").lower()
    if "expense_ratio" in requested and facts.get("expense_ratio"):
        sentences.append(f"The expense ratio for {short_name} is {facts['expense_ratio']}.")
    if "aum" in requested and facts.get("aum"):
        sentences.append(f"The fund size (AUM) for {short_name} is {facts['aum']}.")
    if "nav" in requested and facts.get("nav"):
        nav_val = facts["nav"].split("(")[0].strip()
        as_of = ""
        if "(" in facts["nav"]:
            as_of = " " + facts["nav"][facts["nav"].index("(") :].strip()
        sentences.append(f"The latest NAV for {short_name} is {nav_val}{as_of}.")
    if "risk_level" in requested and facts.get("risk_level"):
        sentences.append(f"The risk level for {short_name} is {facts['risk_level']}.")
    if "holdings" in requested and facts.get("holdings_excerpt"):
        sentences.append(
            f"Top holdings for {short_name} include: {facts['holdings_excerpt'][:500]}"
        )
    if "equity_exposure" in requested and facts.get("equity_exposure_summary"):
        sentences.append(f"For {short_name}, {facts['equity_exposure_summary']}")
    if "exit_load" in requested and facts.get("exit_load"):
        sentences.append(f"The exit load for {short_name} is {facts['exit_load']}.")
    if not sentences and "manager" in q and facts.get("fund_manager"):
        sentences.append(f"The current fund manager for {short_name} is {facts['fund_manager']}.")
    return sentences


def _build_comparison_table(
    groups: List[Tuple[str, List[Dict[str, Any]]]],
    requested: List[str],
) -> str:
    attrs = requested or ["expense_ratio"]
    headers = ["Fund"] + [
        {
            "expense_ratio": "Expense Ratio",
            "aum": "Fund Size (AUM)",
            "nav": "Latest NAV",
            "risk_level": "Risk",
            "holdings": "Holdings (excerpt)",
        }.get(a, a)
        for a in attrs
    ]
    rows: List[List[str]] = []
    for scheme, chunks in groups:
        facts = _merge_facts(chunks)
        short = _short_scheme_name(scheme)
        row = [short]
        for attr in attrs:
            if attr == "holdings":
                val = (facts.get("holdings_excerpt") or "")[:120]
                if val:
                    val += "…"
            else:
                val = facts.get(attr) or ""
            row.append(str(val) if val else "—")
        rows.append(row)
    lines = [" | ".join(headers), " | ".join(["---"] * len(headers))]
    for row in rows:
        lines.append(" | ".join(row))
    return "\n".join(lines)


def build_extractive_answer(
    query: str,
    results: List[Dict[str, Any]],
    intent: Optional[str] = None,
    filters: Optional[Dict[str, Any]] = None,
    requested_attributes: Optional[List[str]] = None,
) -> Optional[str]:
    """
    Answer from structured fields only (no raw HTML dumps).
    Supports multiple requested attributes and multi-fund comparisons.
    """
    q = (query or "").lower()
    if "top 100" in q and (intent == "expense_ratio" or "expense" in q):
        return (
            "HDFC Top 100 Fund is not in the indexed corpus (15 Groww scheme pages). "
            "Add its Groww URL to the fetcher config and run corpus refresh to answer TER for that fund."
        )
    if "midcap opportunities" in q.replace("-", " ") or "mid cap opportunities" in q:
        if "mid cap fund direct" not in q.replace("opportunities", "").strip():
            pass  # may still answer with HDFC Mid Cap Fund if matched

    requested = requested_attributes or detect_requested_attributes(query)
    if not requested and intent:
        requested = [intent]

    groups = _pick_relevant_groups(
        query, _group_by_scheme(results), filters=filters
    )
    if not groups:
        return None

    filter_schemes = _filters_list_schemes(filters)
    if filter_schemes and is_comparison_query(query):
        missing = [s for s in filter_schemes if s not in {g[0] for g in groups}]
        if "midcap opportunities" in q and missing:
            note = (
                "Note: HDFC Midcap Opportunities Fund is not in the indexed corpus; "
                "HDFC Mid Cap Fund is shown where applicable. "
            )
        else:
            note = ""
        table = _build_comparison_table(groups, requested)
        if table and "|" in table:
            return note + "Comparison:\n\n" + table

    if len(groups) == 1:
        scheme, chunks = groups[0]
        facts = _merge_facts(chunks)
        short_name = _short_scheme_name(scheme)
        sentences = _build_single_fund_sentences(short_name, facts, requested, query)
        if not sentences:
            return None
        return " ".join(sentences[:6])

    if is_comparison_query(query) or len(groups) > 1:
        table = _build_comparison_table(groups, requested)
        if table:
            return "Comparison:\n\n" + table

    sentences: List[str] = []
    for scheme, chunks in groups[:4]:
        facts = _merge_facts(chunks)
        short = _short_scheme_name(scheme)
        parts = _build_single_fund_sentences(short, facts, requested, query)
        if parts:
            sentences.append(" ".join(parts))
    if not sentences:
        return None
    return " ".join(sentences[:6])
