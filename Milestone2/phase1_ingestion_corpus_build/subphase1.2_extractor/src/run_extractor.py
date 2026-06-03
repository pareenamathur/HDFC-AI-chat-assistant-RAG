"""
Run Phase 1.2 Extractor — HTML → JSON (uses fetch_manifest for canonical Groww URLs).
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

MILESTONE2_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = MILESTONE2_ROOT / "data"
sys.path.insert(0, str(MILESTONE2_ROOT / "phase1_ingestion_corpus_build" / "subphase1.1_fetcher" / "src"))

from amfi_nav import apply_fetch_manifest_nav
from fetch_manifest import load_manifest, url_for_html_file
from html_extractor import HTMLExtractor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> int:
    logger.info("Starting Phase 1.2 Extractor...")
    extractor = HTMLExtractor()
    html_dir = DATA_DIR / "html"
    processed_dir = DATA_DIR / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)

    manifest = load_manifest(DATA_DIR)
    manifest_by_html = {
        e.get("html_file"): e
        for e in (manifest.get("entries") or [])
        if e.get("html_file") and not e.get("error")
    }
    manifest_files = set(manifest_by_html.keys())
    if manifest_files:
        html_files = [html_dir / name for name in sorted(manifest_files) if (html_dir / name).is_file()]
    else:
        html_files = list(html_dir.glob("*.html"))
    logger.info("Found %s HTML files to extract", len(html_files))

    extracted_data = []
    for html_file in html_files:
        logger.info("Processing: %s", html_file.name)
        try:
            html_content = html_file.read_text(encoding="utf-8")
            page_url = url_for_html_file(DATA_DIR, html_file.name) or ""
            result = extractor.extract_html(html_content, page_url or str(html_file))
            sd = dict(result.structured_data or {})
            mentry = manifest_by_html.get(html_file.name)
            if mentry:
                from groww_parser import parse_groww_mf_page, format_nav_corpus_line

                groww = parse_groww_mf_page(html_content, page_url or "")
                merged = apply_fetch_manifest_nav(groww, mentry)
                if merged.get("nav_as_of"):
                    sd["nav_as_of"] = merged["nav_as_of"]
                if merged.get("nav"):
                    sd["nav"] = str(merged["nav"])
                if merged.get("nav_date_raw"):
                    sd["nav_date"] = merged["nav_date_raw"]
                if merged.get("nav_date_display"):
                    sd["nav_date_display"] = merged["nav_date_display"]
                if merged.get("nav_source"):
                    sd["nav_source"] = merged["nav_source"]
                prefix = format_nav_corpus_line(merged)
                body = result.text
                if prefix and not body.startswith(prefix[:40]):
                    result.text = prefix + "\n\n" + body
            if page_url:
                sd["page_url"] = page_url

            extracted_data.append(
                {
                    "filename": html_file.name,
                    "source_url": page_url or html_file.name,
                    "scheme_name": result.scheme_name,
                    "text": result.text,
                    "structured_data": sd,
                    "document_links": result.document_links,
                }
            )
            logger.info("Extracted: %s (url=%s)", result.scheme_name, page_url[:60] if page_url else "n/a")
        except Exception as e:
            logger.error("Error processing %s: %s", html_file.name, e)

    output_file = processed_dir / "extracted_data_phase1.2.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(extracted_data, f, indent=2, ensure_ascii=False)

    logger.info("Extracted data saved to: %s", output_file)
    return 0 if extracted_data else 1


if __name__ == "__main__":
    raise SystemExit(main())
