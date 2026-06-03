#!/usr/bin/env python3
"""Audit live NAV dates from Groww urls.yaml + AMFI (mfapi.in) overlay."""
from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "phase1_ingestion_corpus_build/subphase1.1_fetcher/src"))
sys.path.insert(0, str(ROOT / "phase1_ingestion_corpus_build/subphase1.2_extractor/src"))

from amfi_nav import fetch_latest_amfi_nav, load_amfi_scheme_codes, merge_nav_sources  # noqa: E402
from groww_parser import extract_next_data_json, parse_groww_mf_page  # noqa: E402
from web_scraper import WebScraper  # noqa: E402


def main() -> int:
    with open(
        ROOT / "phase1_ingestion_corpus_build/subphase1.1_fetcher/config/urls.yaml",
        encoding="utf-8",
    ) as f:
        urls = yaml.safe_load(f).get("urls") or []

    scraper = WebScraper(request_delay=1.0)
    amfi_codes = load_amfi_scheme_codes()
    today = datetime.now(timezone.utc).date().isoformat()
    print(f"Audit date (UTC): {today}\n")
    print("| URL | Latest NAV date | Parsing status |")
    print("| --- | --- | --- |")

    for i, e in enumerate(urls):
        url = e["url"]
        name = e.get("name") or url
        if i:
            time.sleep(1)
        r = scraper.scrape_url(url)
        if r.error or not r.html:
            print(f"| {url} | — | FAIL fetch: {r.error} |")
            continue
        groww = parse_groww_mf_page(r.html, url)
        nd = extract_next_data_json(r.html)
        amfi = fetch_latest_amfi_nav(amfi_codes[name]) if name in amfi_codes else None
        merged, source = merge_nav_sources(groww, amfi)
        if merged.get("nav_as_of"):
            status = f"OK ({source}, __NEXT_DATA__={'yes' if nd else 'no'})"
            latest = merged["nav_as_of"]
        elif nd:
            status = "PARTIAL (__NEXT_DATA__ present, NAV date missing)"
            latest = "—"
        else:
            status = "FAIL (no __NEXT_DATA__ / mfServerSideData)"
            latest = "—"
        short_url = url.replace("https://groww.in/mutual-funds/", "groww.in/…/")
        print(f"| {short_url} | {latest} | {status} |")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
