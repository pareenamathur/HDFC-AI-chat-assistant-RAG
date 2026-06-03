"""
Run the Phase 1.3 Cleaner & Normalizer to clean and normalize extracted data.
"""

import sys
import os
import json
from pathlib import Path

# Add src directory to path
sys.path.insert(0, os.path.dirname(__file__))

from data_cleaner import DataCleaner
from metadata_tagger import MetadataTagger
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[2] / "subphase1.2_extractor" / "src"),
)
from groww_parser import format_nav_corpus_line  # noqa: E402


def _reinject_canonical_nav_line(
    text: str, scheme_name: str, metadata: dict
) -> str:
    """Prepend parser canonical NAV line so chunk regex + retrieval see freshest as-of."""
    nav = metadata.get("nav")
    nav_as_of = metadata.get("nav_as_of")
    if not nav or not nav_as_of:
        return text
    disp = metadata.get("nav_date_display")
    if not disp:
        try:
            d = datetime.strptime(str(nav_as_of)[:10], "%Y-%m-%d").date()
            disp = d.strftime("%d %b %y")
        except ValueError:
            return text
    prefix = format_nav_corpus_line(
        {"scheme_name": scheme_name, "nav": str(nav), "nav_date_display": disp}
    )
    if not prefix:
        return text
    stripped = text.lstrip()
    if stripped.startswith(prefix[: min(len(prefix), 48)]):
        return text
    return prefix + "\n\n" + text


def _reinject_scheme_facts_lines(text: str, metadata: dict) -> str:
    """Prepend TER / exit load so retrieval and extractive paths can match fee intents."""
    lines: list[str] = []
    er = metadata.get("expense_ratio")
    if er is not None and str(er).strip():
        er_s = str(er).strip()
        if "%" not in er_s:
            er_s = f"{er_s}%"
        lines.append(f"Total Expense Ratio (TER): {er_s}")
    xl = metadata.get("exit_load")
    if xl is not None and str(xl).strip():
        xl_s = str(xl).strip()
        if "%" not in xl_s and not xl_s.lower().endswith("%"):
            xl_s = f"{xl_s}%"
        lines.append(f"Exit load: {xl_s}")
    risk = metadata.get("risk_level")
    if risk:
        lines.append(f"Risk level: {risk}")
    if not lines:
        return text
    block = " | ".join(lines)
    if block[:40] in text:
        return text
    return block + "\n\n" + text


def main():
    """Run the cleaner and normalizer to process extracted data."""
    logger.info("Starting Phase 1.3 Cleaner & Normalizer...")

    # Initialize cleaner and tagger
    cleaner = DataCleaner()
    tagger = MetadataTagger()

    # Processed data directory (relative to script location)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    processed_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(script_dir))), 'data', 'processed')
    
    # Load extracted data from Phase 1.2
    input_file = os.path.join(processed_dir, 'extracted_data_phase1.2.json')
    
    with open(input_file, 'r', encoding='utf-8') as f:
        extracted_data = json.load(f)
    
    logger.info(f"Loaded {len(extracted_data)} documents from Phase 1.2")
    
    cleaned_data = []
    
    for doc in extracted_data:
        logger.info(f"Processing: {doc['scheme_name']}")
        
        try:
            # Clean text (includes normalization internally)
            cleaned_result = cleaner.clean_text(doc['text'])
            
            # Extract cleaned text
            final_text = cleaned_result.cleaned_text
            
            # Remove headers/footers
            final_text = cleaner.remove_headers_footers(final_text)
            
            # Normalize dates
            final_text = cleaner.normalize_dates(final_text)

            # Clean metadata
            cleaned_metadata = cleaner.clean_metadata(doc.get('structured_data', {}))

            final_text = _reinject_canonical_nav_line(
                final_text, doc["scheme_name"], cleaned_metadata
            )
            final_text = _reinject_scheme_facts_lines(final_text, cleaned_metadata)
            
            page_url = doc.get('source_url') or doc.get('filename', '')
            cleaned_metadata = dict(cleaned_metadata)
            if page_url.startswith('http'):
                cleaned_metadata['page_url'] = page_url

            # Create document for tagging
            document = {
                'text': final_text,
                'metadata': {
                    'scheme_name': doc['scheme_name'],
                    'document_type': 'html',
                    'source_url': page_url,
                    'category': 'mutual_fund'
                }
            }
            
            # Tag with metadata
            tagged_doc = tagger.tag_document(
                scheme_name=doc['scheme_name'],
                document_type='html',
                source_url=page_url,
                content=final_text,
                category='mutual_fund',
                additional_metadata=cleaned_metadata,
            )
            
            cleaned_data.append({
                'filename': doc['filename'],
                'scheme_name': doc['scheme_name'],
                'text': final_text,
                'cleaned_metadata': cleaned_metadata,
                'document_id': tagged_doc.document_id,
                'metadata': tagged_doc.metadata,
                'content_hash': tagged_doc.content_hash
            })
            
            logger.info(f"Cleaned and tagged: {doc['scheme_name']}")
            
        except Exception as e:
            logger.error(f"Error processing {doc['scheme_name']}: {str(e)}")
    
    # Save cleaned data to JSON
    output_file = os.path.join(processed_dir, 'cleaned_data_phase1.3.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(cleaned_data, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Cleaned data saved to: {output_file}")
    logger.info(f"Phase 1.3 Cleaner & Normalizer complete!")


if __name__ == "__main__":
    main()
