"""Persist per-URL fetch diagnostics (status, NAV as-of, HTML path)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

MANIFEST_NAME = "fetch_manifest.json"


def manifest_path(data_dir: Path) -> Path:
    return data_dir / MANIFEST_NAME


def load_manifest(data_dir: Path) -> Dict[str, Any]:
    path = manifest_path(data_dir)
    if not path.is_file():
        return {"fetched_at": None, "entries": []}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_manifest(data_dir: Path, entries: List[Dict[str, Any]]) -> Path:
    data_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "entries": entries,
    }
    path = manifest_path(data_dir)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return path


def url_for_html_file(data_dir: Path, html_basename: str) -> str | None:
    m = load_manifest(data_dir)
    for e in m.get("entries") or []:
        if e.get("html_file") == html_basename and e.get("url"):
            return str(e["url"])
    return None
