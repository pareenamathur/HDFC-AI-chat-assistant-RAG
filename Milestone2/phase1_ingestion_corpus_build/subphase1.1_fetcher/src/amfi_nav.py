"""
AMFI daily NAV via mfapi.in (aggregates official AMFI publication).
Used to overlay fresher NAV than Groww __NEXT_DATA__ when the HTML snapshot lags.
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import requests
import yaml

logger = logging.getLogger(__name__)

_MFAPI_BASE = "https://api.mfapi.in/mf"
_TIMEOUT = 30


def _config_path() -> Path:
    return Path(__file__).resolve().parent.parent / "config" / "amfi_scheme_codes.yaml"


def load_amfi_scheme_codes() -> Dict[str, int]:
    path = _config_path()
    if not path.is_file():
        return {}
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    out: Dict[str, int] = {}
    for name, code in (data.get("schemes") or {}).items():
        if name and code is not None:
            out[str(name)] = int(code)
    return out


def parse_amfi_nav_date(raw: str) -> Optional[date]:
    """AMFI/mfapi uses DD-MM-YYYY."""
    if not raw:
        return None
    try:
        return datetime.strptime(str(raw).strip(), "%d-%m-%Y").date()
    except ValueError:
        return None


def fetch_latest_amfi_nav(scheme_code: int, retries: int = 2) -> Optional[Dict[str, Any]]:
    r = None
    for attempt in range(1, retries + 2):
        try:
            r = requests.get(f"{_MFAPI_BASE}/{scheme_code}/latest", timeout=_TIMEOUT)
            break
        except requests.RequestException as e:
            if attempt <= retries:
                logger.warning("AMFI retry %s/%s for scheme %s", attempt, retries, scheme_code)
                continue
            logger.warning("AMFI fetch failed for %s: %s", scheme_code, e)
            return None
    if r is None:
        return None
    if not r.ok:
        logger.warning("AMFI latest HTTP %s for scheme %s", r.status_code, scheme_code)
        return None
    payload = r.json()
    row = (payload.get("data") or [None])[0]
    if not isinstance(row, dict):
        return None
    nav_d = parse_amfi_nav_date(row.get("date", ""))
    nav_val = row.get("nav")
    if nav_d is None or nav_val is None:
        return None
    meta = payload.get("meta") or {}
    return {
        "scheme_code": scheme_code,
        "scheme_name_amfi": meta.get("scheme_name"),
        "nav": str(nav_val),
        "nav_date_raw": row.get("date"),
        "nav_as_of": nav_d.isoformat(),
        "nav_source": "amfi",
    }


def merge_nav_sources(
    groww: Dict[str, Any], amfi: Optional[Dict[str, Any]]
) -> Tuple[Dict[str, Any], str]:
    """
    Return merged groww-like dict and nav_source label (groww | amfi | groww+amfi).
    Prefer the source with the newer nav_as_of; AMFI wins on tie.
    """
    if not amfi or not amfi.get("nav_as_of"):
        out = dict(groww)
        out["nav_source"] = "groww"
        return out, "groww"

    g_date = None
    if groww.get("nav_as_of"):
        try:
            g_date = datetime.strptime(groww["nav_as_of"], "%Y-%m-%d").date()
        except ValueError:
            pass
    try:
        a_date = datetime.strptime(amfi["nav_as_of"], "%Y-%m-%d").date()
    except ValueError:
        a_date = None

    if a_date and (g_date is None or a_date >= g_date):
        out = dict(groww)
        out["nav"] = amfi["nav"]
        out["nav_date_raw"] = amfi.get("nav_date_raw")
        out["nav_as_of"] = amfi["nav_as_of"]
        out["nav_date_display"] = a_date.strftime("%d %b %y")
        out["nav_source"] = "amfi"
        out["amfi_scheme_code"] = amfi.get("scheme_code")
        out["extraction_ok"] = True
        return out, "amfi"

    out = dict(groww)
    out["nav_source"] = "groww"
    return out, "groww"


def apply_fetch_manifest_nav(
    groww: Dict[str, Any], manifest_entry: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """Prefer NAV fields from fetch_manifest when newer than HTML __NEXT_DATA__."""
    if not manifest_entry or not manifest_entry.get("nav_as_of"):
        return groww
    try:
        m_date = datetime.strptime(manifest_entry["nav_as_of"], "%Y-%m-%d").date()
    except ValueError:
        return groww
    g_date = None
    if groww.get("nav_as_of"):
        try:
            g_date = datetime.strptime(groww["nav_as_of"], "%Y-%m-%d").date()
        except ValueError:
            pass
    if g_date is not None and g_date > m_date:
        return groww
    out = dict(groww)
    for key in ("nav", "nav_date_raw", "nav_as_of", "nav_source", "amfi_scheme_code"):
        if manifest_entry.get(key) is not None:
            out[key] = manifest_entry[key]
    if m_date:
        out["nav_date_display"] = m_date.strftime("%d %b %y")
    out["extraction_ok"] = True
    return out
