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


def _clean_text(text: str) -> str:
    t = (text or "").strip().replace("\n", " ")
    t = _NOISE_RE.sub("", t)
    t = re.sub(r"\s{2,}", " ", t)
    return t.strip()


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


def _merge_facts(chunks: List[Dict[str, Any]]) -> Dict[str, str]:
    merged: Dict[str, str] = {}
    for res in chunks:
        text = (res.get("text") or "").strip()
        if not text:
            continue
        for k, v in extract_fund_facts(text).items():
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

    blocks: List[str] = []
    for scheme, chunks in groups:
        facts = _merge_facts(chunks)
        lines = [f"=== {scheme} ==="]
        if facts.get("nav"):
            lines.append(f"Latest NAV: {facts['nav']}")
        if facts.get("aum"):
            lines.append(f"AUM: {facts['aum']}")
        if facts.get("expense_ratio"):
            lines.append(f"Expense ratio: {facts['expense_ratio']}")
        if facts.get("exit_load"):
            lines.append(f"Exit load: {facts['exit_load']}")
        if facts.get("fund_manager"):
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
        elif "nav" in q:
            if facts.get("nav"):
                sentences.append(f"The latest NAV for {short_name} is {facts['nav'].split('(')[0].strip()}.")
        elif "nav" in q and facts.get("nav"):
            nav_val = facts["nav"].split("(")[0].strip()
            as_of = ""
            if "(" in facts["nav"]:
                as_of = " " + facts["nav"][facts["nav"].index("(") :].strip()
            sentences.append(f"The latest NAV for {short_name} is {nav_val}{as_of}.")
        elif facts.get("nav"):
            sentences.append(f"The latest NAV for {short_name} is {facts['nav']}.")

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
