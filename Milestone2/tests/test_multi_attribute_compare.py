"""Tests for multi-attribute and multi-fund comparison answers."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "phase2_retrieval_layer" / "src"))
sys.path.insert(0, str(ROOT / "phase3_reasoning_guardrails" / "src"))

from query_processor import QueryProcessor  # noqa: E402
from extractive_fallback import (  # noqa: E402
    build_extractive_answer,
    detect_requested_attributes,
    is_comparison_query,
)


def _load_schemes() -> list[str]:
    path = ROOT / "data" / "processed" / "chunked_data_phase1.4.json"
    with open(path, encoding="utf-8") as f:
        chunks = json.load(f)
    return sorted(
        {c.get("scheme_name") or (c.get("metadata") or {}).get("scheme_name") for c in chunks}
        - {None}
    )


def _mock_result(scheme: str, text: str, **meta_extra) -> dict:
    return {
        "id": f"id-{scheme[:12]}",
        "text": text,
        "metadata": {"scheme_name": scheme, **meta_extra},
        "structured_data": meta_extra,
        "score": 0.9,
    }


@pytest.fixture(scope="module")
def schemes() -> list[str]:
    return _load_schemes()


@pytest.fixture(scope="module")
def qp(schemes: list[str]) -> QueryProcessor:
    return QueryProcessor(schemes)


def test_requested_attributes_fund_size_and_expense():
    attrs = detect_requested_attributes(
        "What is the fund size and expense ratio of HDFC Multicap Fund?"
    )
    assert "aum" in attrs
    assert "expense_ratio" in attrs


def test_comparison_detects_two_funds(qp: QueryProcessor):
    q = "Compare the expense ratio of HDFC Multicap Fund and HDFC Midcap Opportunities Fund."
    proc = qp.process_query(q)
    assert is_comparison_query(q)
    assert proc["intent"] == "expense_ratio"
    sn = proc["filters"].get("scheme_name")
    assert isinstance(sn, dict) and "$in" in sn
    assert len(sn["$in"]) >= 2


def test_single_fund_multi_attribute_answer():
    scheme = "HDFC Multi Cap Fund Direct Growth"
    results = [
        _mock_result(
            scheme,
            "Scheme facts for HDFC Multi Cap Fund Direct Growth:\n"
            "Total Expense Ratio (TER): 0.82%\nFund size (AUM): 19,557.57 Cr",
            expense_ratio="0.82%",
            aum="19557.5716",
            nav="18.90400",
            nav_as_of="2026-06-02",
        ),
    ]
    q = "What is the fund size and expense ratio of HDFC Multicap Fund?"
    attrs = detect_requested_attributes(q)
    ans = build_extractive_answer(
        q,
        results,
        filters={"scheme_name": scheme},
        requested_attributes=attrs,
    )
    assert ans
    assert "0.82%" in ans
    assert "19,557" in ans or "19557" in ans or "fund size" in ans.lower()


def test_expense_comparison_two_funds_table():
    multi = "HDFC Multi Cap Fund Direct Growth"
    mid = "HDFC Mid Cap Fund Direct Growth"
    results = [
        _mock_result(multi, "Scheme facts\nTotal Expense Ratio (TER): 0.82%", expense_ratio="0.82%"),
        _mock_result(mid, "Scheme facts\nTotal Expense Ratio (TER): 0.8%", expense_ratio="0.8%"),
    ]
    q = "Compare the expense ratio of HDFC Multicap Fund and HDFC Mid Cap Fund."
    ans = build_extractive_answer(
        q,
        results,
        filters={"scheme_name": {"$in": [multi, mid]}},
        requested_attributes=["expense_ratio"],
    )
    assert ans
    assert "Comparison" in ans
    assert "0.82%" in ans
    assert "0.8%" in ans
    assert "Multi Cap" in ans
    assert "Mid Cap" in ans


@pytest.mark.parametrize(
    "query,attr",
    [
        ("Compare AUM of HDFC Flexi Cap and HDFC Small Cap Fund", "aum"),
        ("Compare risk of HDFC Balanced Advantage and HDFC Hybrid Debt Fund", "risk_level"),
        ("Compare holdings of HDFC Nifty 50 and HDFC BSE Sensex Index Fund", "holdings"),
    ],
)
def test_comparison_query_parses(qp: QueryProcessor, query: str, attr: str):
    proc = qp.process_query(query)
    assert is_comparison_query(query)
    sn = proc["filters"].get("scheme_name")
    assert sn
    assert attr in proc.get("requested_attributes") or proc.get("intent") == attr
