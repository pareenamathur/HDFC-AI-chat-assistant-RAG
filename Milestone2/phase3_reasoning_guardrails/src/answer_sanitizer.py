"""Strip LLM URL/disclaimer noise; extract NAV as-of dates from scraped chunk text."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

OFFICIAL_HDFC_URL = "https://www.hdfcfund.com/"

# Groq often adds these when prompted for URLs we strip server-side.
_DISCLAIMER_RES = [
    re.compile(r"\[Source\]\s*", re.I),
    re.compile(r"\(Note:[^)]*\)", re.I | re.DOTALL),
    re.compile(r"\(Please note[^)]*\)", re.I | re.DOTALL),
    re.compile(
        r"The exact URL for the specific fund is not provided[^.]*\.?",
        re.I,
    ),
    re.compile(r"website link is available[^.]*\.?", re.I),
    re.compile(r"not provided in the context[^.]*\.?", re.I),
    re.compile(r"https?://\S+", re.I),
]

_NAV_AS_OF_RE = re.compile(
    r"NAV:\s*(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{2})\b",
    re.I,
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


def sanitize_answer_text(answer: str) -> str:
    """Remove URLs and boilerplate disclaimers; keep factual sentences only."""
    text = (answer or "").strip()
    for pat in _DISCLAIMER_RES:
        text = pat.sub(" ", text)
    text = re.sub(r"\s{2,}", " ", text).strip()
    text = re.sub(r"\s+([,.])", r"\1", text)
    return text.strip()


def extract_nav_as_of_from_text(text: str) -> Optional[str]:
    """Parse 'NAV: 05 May 26' → '2026-05-05'."""
    if not text:
        return None
    m = _NAV_AS_OF_RE.search(text)
    if not m:
        return None
    day = int(m.group(1))
    mon = _MONTHS.get(m.group(2).lower()[:3])
    if not mon:
        return None
    yy = int(m.group(3))
    year = 2000 + yy if yy < 80 else 1900 + yy
    return f"{year:04d}-{mon:02d}-{day:02d}"


def extract_data_as_of(results: List[Dict[str, Any]]) -> Optional[str]:
    """Best NAV snapshot date from retrieved chunks (Groww scrape in corpus)."""
    for res in results or []:
        if not isinstance(res, dict):
            continue
        text = res.get("text") or ""
        d = extract_nav_as_of_from_text(text)
        if d:
            return d
        meta = res.get("metadata") or {}
        if isinstance(meta, dict):
            lud = meta.get("last_updated_date") or meta.get("created_at")
            if lud and isinstance(lud, str) and len(lud) >= 10:
                return lud[:10]
    return None


def resolve_source_fields(results: List[Dict[str, Any]]) -> Dict[str, Optional[str]]:
    """Always return a clickable official URL for the UI (metadata is usually HTML basenames)."""
    if not results:
        return {"source": None, "source_link": OFFICIAL_HDFC_URL, "last_updated": None}

    top = results[0]
    meta = top.get("metadata") if isinstance(top, dict) else {}
    if not isinstance(meta, dict):
        meta = {}

    scheme_name = str(meta.get("scheme_name") or "HDFC Mutual Fund")
    raw_url = (meta.get("source_url") or "").strip()
    if raw_url.startswith("http://") or raw_url.startswith("https://"):
        link = raw_url
    else:
        link = OFFICIAL_HDFC_URL

    return {
        "source": scheme_name,
        "source_link": link,
        "last_updated": extract_data_as_of(results),
    }
