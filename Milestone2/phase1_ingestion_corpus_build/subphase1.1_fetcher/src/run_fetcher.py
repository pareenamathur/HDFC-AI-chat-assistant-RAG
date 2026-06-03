"""
Run Phase 1.1 Fetcher — scrape Groww URLs, write HTML + fetch_manifest.json diagnostics.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(
    0,
    str(
        Path(__file__).resolve().parents[2]
        / "subphase1.2_extractor"
        / "src"
    ),
)

from amfi_nav import fetch_latest_amfi_nav, load_amfi_scheme_codes, merge_nav_sources
from config import ConfigManager, get_config
from fetch_manifest import save_manifest
from groww_parser import parse_groww_mf_page
from web_scraper import WebScraper

NAV_STALE_FAIL_DAYS = 7

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MILESTONE2_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = MILESTONE2_ROOT / "data"


def _safe_filename(scheme_name: str) -> str:
    return scheme_name.replace(" ", "_").replace("/", "_").replace("&", "and")[:180]


def _load_url_entries() -> list[dict]:
    mgr = ConfigManager()
    with open(mgr.urls_config_file, encoding="utf-8") as f:
        import yaml

        cfg = yaml.safe_load(f) or {}
    entries = []
    for item in cfg.get("urls") or []:
        if isinstance(item, dict) and item.get("url"):
            entries.append(item)
        elif isinstance(item, str):
            entries.append({"url": item, "name": item})
    return entries


def main() -> int:
    logger.info("Starting Phase 1.1 Fetcher...")
    config = get_config()
    scraper = WebScraper(
        user_agent=config.user_agent,
        request_delay=config.request_delay,
        timeout=config.timeout,
        max_retries=3,
    )

    url_entries = _load_url_entries()
    if not url_entries:
        logger.error("No URLs in urls.yaml")
        return 1

    html_output_dir = Path(config.output_dir)
    html_output_dir.mkdir(parents=True, exist_ok=True)

    manifest_entries: list[dict] = []
    ok_count = 0
    stale_count = 0
    today = datetime.now(timezone.utc).date()
    amfi_codes = load_amfi_scheme_codes()

    for i, entry in enumerate(url_entries):
        url = entry["url"]
        name = entry.get("name") or url
        if i > 0:
            time.sleep(config.request_delay)

        result = scraper.scrape_url(url)
        fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        row: dict = {
            "url": url,
            "name": name,
            "fetched_at": fetched_at,
            "status_code": result.status_code,
            "error": result.error,
            "html_file": None,
            "scheme_name": result.scheme_name,
            "nav": None,
            "nav_as_of": None,
            "nav_date_raw": None,
            "extraction_ok": False,
            "extraction_error": None,
            "nav_stale": False,
            "nav_age_days": None,
            "nav_source": None,
            "amfi_scheme_code": amfi_codes.get(name),
        }

        if result.html and not result.error:
            groww = parse_groww_mf_page(result.html, url)
            amfi = None
            code = amfi_codes.get(name)
            if code:
                amfi = fetch_latest_amfi_nav(code)
            groww, nav_source = merge_nav_sources(groww, amfi)
            scheme = groww.get("scheme_name") or result.scheme_name or name
            fname = f"{_safe_filename(scheme)}.html"
            filepath = html_output_dir / fname
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(result.html)
            row["html_file"] = fname
            row["scheme_name"] = scheme
            row["nav"] = groww.get("nav")
            row["nav_as_of"] = groww.get("nav_as_of")
            row["nav_date_raw"] = groww.get("nav_date_raw")
            row["extraction_ok"] = groww.get("extraction_ok")
            row["extraction_error"] = groww.get("extraction_error")
            row["nav_source"] = nav_source
            if groww.get("nav_as_of"):
                try:
                    nav_d = datetime.strptime(groww["nav_as_of"], "%Y-%m-%d").date()
                    age = (today - nav_d).days
                    row["nav_age_days"] = age
                    row["nav_stale"] = age > NAV_STALE_FAIL_DAYS
                    if row["nav_stale"]:
                        stale_count += 1
                except ValueError:
                    pass
            ok_count += 1
            logger.info(
                "Saved %s | nav=%s as_of=%s extraction_ok=%s",
                fname,
                row["nav"],
                row["nav_as_of"],
                row["extraction_ok"],
            )
        else:
            logger.error("Fetch failed %s: %s", url, result.error)

        manifest_entries.append(row)

    manifest_path = save_manifest(DATA_DIR, manifest_entries)
    logger.info(
        "Phase 1.1 complete — ok=%s/%s stale_nav=%s manifest=%s",
        ok_count,
        len(url_entries),
        stale_count,
        manifest_path,
    )

    failed = [e for e in manifest_entries if e.get("error")]
    if failed:
        logger.warning("%s URLs failed — see %s", len(failed), manifest_path)
        for e in failed:
            logger.warning("  FAIL %s — %s", e.get("url"), e.get("error"))

    if ok_count == 0:
        return 1

    nav_dates = [
        datetime.strptime(e["nav_as_of"], "%Y-%m-%d").date()
        for e in manifest_entries
        if e.get("nav_as_of") and not e.get("error")
    ]
    if nav_dates:
        max_age = (today - max(nav_dates)).days
        logger.info(
            "NAV as-of max=%s age_days=%s threshold=%s",
            max(nav_dates).isoformat(),
            max_age,
            NAV_STALE_FAIL_DAYS,
        )
        if max_age > NAV_STALE_FAIL_DAYS:
            logger.error(
                "Newest NAV is %s days old (>%s) — AMFI/Groww sources not current",
                max_age,
                NAV_STALE_FAIL_DAYS,
            )
            return 1
    elif ok_count:
        logger.error("Fetched pages but no NAV as-of dates extracted")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
