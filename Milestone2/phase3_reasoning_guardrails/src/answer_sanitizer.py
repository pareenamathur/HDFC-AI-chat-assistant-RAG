"""Strip LLM URL/disclaimer noise; resolve source links from retrieved chunk metadata."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

OFFICIAL_HDFC_URL = "https://www.hdfcfund.com/"

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

_FETCH_MANIFEST_CACHE: Optional[Dict[str, str]] = None


def _load_html_to_url_map() -> Dict[str, str]:
    global _FETCH_MANIFEST_CACHE
    if _FETCH_MANIFEST_CACHE is not None:
        return _FETCH_MANIFEST_CACHE
    mapping: Dict[str, str] = {}
    try:
        base = Path(__file__).resolve().parents[2]
        path = base / "data" / "fetch_manifest.json"
        if path.is_file():
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            for e in data.get("entries") or []:
                hf = e.get("html_file")
                url = e.get("url")
                if hf and url:
                    mapping[str(hf)] = str(url)
    except (OSError, json.JSONDecodeError):
        pass
    _FETCH_MANIFEST_CACHE = mapping
    return mapping


def _resolve_page_url(meta: Dict[str, Any]) -> Optional[str]:
    for key in ("page_url", "source_url"):
        raw = (meta.get(key) or "").strip()
        if raw.startswith("http://") or raw.startswith("https://"):
            return raw
    raw = (meta.get("source_url") or "").strip()
    if raw.endswith(".html"):
        return _load_html_to_url_map().get(raw) or _load_html_to_url_map().get(Path(raw).name)
    return None


def sanitize_answer_text(answer: str) -> str:
    text = (answer or "").strip()
    for pat in _DISCLAIMER_RES:
        text = pat.sub(" ", text)
    text = re.sub(r"\s{2,}", " ", text).strip()
    text = re.sub(r"\s+([,.])", r"\1", text)
    return text.strip()


def extract_nav_as_of_from_text(text: str) -> Optional[str]:
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
    best: Optional[str] = None
    for res in results or []:
        if not isinstance(res, dict):
            continue
        meta = res.get("metadata") or {}
        if isinstance(meta, dict) and meta.get("nav_as_of"):
            cand = str(meta["nav_as_of"])[:10]
        else:
            cand = extract_nav_as_of_from_text(res.get("text") or "")
        if not cand:
            continue
        if best is None or cand > best:
            best = cand
    return best


def collect_sources_from_results(
    results: List[Dict[str, Any]], *, max_sources: int = 5
) -> List[Dict[str, Optional[str]]]:
    """Unique Groww/fund page links from retrieved chunks (no hallucinated URLs)."""
    seen: set[str] = set()
    out: List[Dict[str, Optional[str]]] = []
    for res in results or []:
        if not isinstance(res, dict):
            continue
        meta = res.get("metadata") if isinstance(res.get("metadata"), dict) else {}
        link = _resolve_page_url(meta)
        if not link or link in seen:
            continue
        seen.add(link)
        scheme = str(meta.get("scheme_name") or "HDFC Mutual Fund")
        title = scheme
        nav_as_of = meta.get("nav_as_of") or extract_nav_as_of_from_text(res.get("text") or "")
        out.append(
            {
                "title": title,
                "url": link,
                "scheme_name": scheme,
                "nav_as_of": str(nav_as_of) if nav_as_of else None,
            }
        )
        if len(out) >= max_sources:
            break
    return out


def resolve_source_fields(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    sources = collect_sources_from_results(results)
    if not results:
        return {
            "source": None,
            "source_link": OFFICIAL_HDFC_URL,
            "last_updated": None,
            "sources": [],
        }

    if sources:
        primary = sources[0]
        return {
            "source": primary.get("title") or primary.get("scheme_name"),
            "source_link": primary.get("url") or OFFICIAL_HDFC_URL,
            "last_updated": extract_data_as_of(results),
            "sources": sources,
        }

    top = results[0]
    meta = top.get("metadata") if isinstance(top, dict) else {}
    if not isinstance(meta, dict):
        meta = {}
    scheme_name = str(meta.get("scheme_name") or "HDFC Mutual Fund")
    return {
        "source": scheme_name,
        "source_link": OFFICIAL_HDFC_URL,
        "last_updated": extract_data_as_of(results),
        "sources": [],
    }
