"""
Parse Groww mutual-fund pages: NAV and fund facts live in __NEXT_DATA__ (not always in visible text).
"""
from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

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


def _parse_nav_date(raw: str) -> Optional[date]:
    """Groww uses formats like 08-May-2026 or 08 May 26."""
    if not raw:
        return None
    s = str(raw).strip()
    for fmt in ("%d-%b-%Y", "%d-%B-%Y", "%d %b %y", "%d %b %Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    m = re.match(r"(\d{1,2})[-\s]([A-Za-z]{3,9})[-\s](\d{2,4})", s)
    if not m:
        return None
    day = int(m.group(1))
    mon = _MONTHS.get(m.group(2).lower()[:3])
    if not mon:
        return None
    yy = int(m.group(3))
    year = yy if yy > 99 else (2000 + yy if yy < 80 else 1900 + yy)
    try:
        return date(year, mon, day)
    except ValueError:
        return None


def _nav_display(d: date) -> str:
    return d.strftime("%d %b %y")


def extract_next_data_json(html: str) -> Optional[Dict[str, Any]]:
    if not html or "__NEXT_DATA__" not in html:
        return None
    m = re.search(r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError as e:
        logger.warning("Failed to parse __NEXT_DATA__ JSON: %s", e)
        return None


def parse_groww_mf_page(html: str, page_url: str = "") -> Dict[str, Any]:
    """
    Extract mfServerSideData from a Groww scheme page.
    Returns dict with nav, nav_date, isin, scheme_name, page_url, extraction_ok, etc.
    """
    out: Dict[str, Any] = {
        "page_url": page_url,
        "extraction_ok": False,
        "extraction_error": None,
    }
    data = extract_next_data_json(html)
    if not data:
        out["extraction_error"] = "missing_or_invalid___NEXT_DATA__"
        return out

    try:
        mf = data["props"]["pageProps"]["mfServerSideData"]
    except (KeyError, TypeError):
        out["extraction_error"] = "mfServerSideData_missing"
        return out

    if not isinstance(mf, dict):
        out["extraction_error"] = "mfServerSideData_not_dict"
        return out

    scheme = str(mf.get("scheme_name") or mf.get("fund_name") or "").strip()
    nav_val = mf.get("nav")
    nav_date_raw = mf.get("nav_date") or mf.get("nav_as_on") or mf.get("nav_as_on_date")
    nav_d = _parse_nav_date(str(nav_date_raw) if nav_date_raw else "")

    out["scheme_name"] = scheme
    out["search_id"] = mf.get("search_id")
    out["isin"] = mf.get("isin") or mf.get("groww_scheme_code")
    out["nav"] = str(nav_val) if nav_val is not None else None
    out["nav_date_raw"] = str(nav_date_raw) if nav_date_raw else None
    out["nav_as_of"] = nav_d.isoformat() if nav_d else None
    out["nav_date_display"] = _nav_display(nav_d) if nav_d else None
    out["expense_ratio"] = mf.get("expense_ratio")
    out["aum"] = mf.get("aum") or mf.get("fund_size")
    out["risk"] = mf.get("risk") or mf.get("risk_level")
    out["category"] = mf.get("category")
    out["extraction_ok"] = bool(nav_val is not None or nav_d)
    return out


def format_nav_corpus_line(parsed: Dict[str, Any]) -> str:
    """Canonical NAV line embedded in chunk text for retrieval + staleness checks."""
    scheme = parsed.get("scheme_name") or "Fund"
    nav = parsed.get("nav")
    disp = parsed.get("nav_date_display")
    if nav and disp:
        return f"{scheme} | NAV: {disp} ₹{nav}"
    if nav:
        return f"{scheme} | NAV: ₹{nav}"
    return scheme
