"""
Run the Phase 1.4 Chunker to chunk cleaned data.
"""

import sys
import os
import json
import hashlib
import uuid
from pathlib import Path

# Add src directory to path
sys.path.insert(0, os.path.dirname(__file__))

from chunker import Chunker
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _format_ter(raw: object) -> str:
    s = str(raw or "").strip()
    if not s:
        return ""
    return s if "%" in s else f"{s}%"


def _build_facts_chunk(doc: dict) -> dict | None:
    """One high-signal chunk per scheme for NAV / TER / exit load (vector-friendly)."""
    sd = doc.get("cleaned_metadata") or doc.get("structured_data") or {}
    meta = doc.get("metadata") or {}
    scheme = doc.get("scheme_name") or meta.get("scheme_name")
    if not scheme:
        return None
    lines = [f"Scheme facts for {scheme}:"]
    nav = sd.get("nav")
    nav_as_of = sd.get("nav_as_of")
    if nav and nav_as_of:
        lines.append(f"Latest NAV: {nav_as_of} ₹{nav}")
    ter = _format_ter(sd.get("expense_ratio"))
    if ter:
        lines.append(f"Total Expense Ratio (TER): {ter}")
    xl = sd.get("exit_load")
    if xl:
        xl_s = str(xl).strip()
        if "%" not in xl_s:
            xl_s = f"{xl_s}%"
        lines.append(f"Exit load: {xl_s}")
    if sd.get("risk_level"):
        lines.append(f"Risk level: {sd['risk_level']}")
    if sd.get("category"):
        lines.append(f"Category: {sd['category']}")
    lines.append("Portfolio holdings table is available on the source page (Holdings section).")
    text = "\n".join(lines)
    doc_id = meta.get("document_id") or str(uuid.uuid4())
    chunk_meta = dict(meta)
    chunk_meta["section"] = "scheme_facts"
    chunk_meta["chunk_number"] = 0
    chunk_meta["chunk_length"] = len(text)
    if ter:
        chunk_meta["expense_ratio"] = ter
    return {
        "chunk_id": f"{doc_id}_facts",
        "text": text,
        "section": "scheme_facts",
        "source_document_id": doc_id,
        "metadata": chunk_meta,
        "structured_data": {k: v for k, v in sd.items() if v},
        "scheme_name": scheme,
    }


def _dedupe_chunks(chunks: list) -> list:
    seen: set[str] = set()
    out: list = []
    for c in chunks:
        text = (c.get("text") or "").strip()
        if len(text) < 40:
            continue
        h = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()
        if h in seen:
            continue
        seen.add(h)
        out.append(c)
    return out


def main():
    """Run the chunker to process cleaned data."""
    logger.info("Starting Phase 1.4 Chunker...")

    # Initialize chunker
    chunker = Chunker(min_chunk_size=50, max_chunk_size=1000, chunk_overlap=100)

    # Processed data directory (relative to script location)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    processed_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(script_dir))), 'data', 'processed')
    
    # Load cleaned data from Phase 1.3
    input_file = os.path.join(processed_dir, 'cleaned_data_phase1.3.json')
    
    with open(input_file, 'r', encoding='utf-8') as f:
        cleaned_data = json.load(f)
    
    logger.info(f"Loaded {len(cleaned_data)} documents from Phase 1.3")
    
    all_chunks = []
    
    for doc in cleaned_data:
        logger.info(f"Chunking: {doc['scheme_name']}")
        
        try:
            # Chunk the document
            chunks = chunker.chunk_document(
                text=doc['text'],
                sections={},  # No sections available from HTML extraction
                structured_data=doc['cleaned_metadata'],
                document_metadata=doc['metadata']
            )
            
            # Convert chunks to dict for JSON serialization
            for chunk in chunks:
                all_chunks.append({
                    'chunk_id': chunk.chunk_id,
                    'text': chunk.text,
                    'section': chunk.section,
                    'source_document_id': chunk.source_document_id,
                    'metadata': chunk.metadata,
                    'structured_data': chunk.structured_data,
                    'scheme_name': doc['scheme_name']
                })
            
            logger.info(f"Created {len(chunks)} chunks")

            facts = _build_facts_chunk(doc)
            if facts:
                all_chunks.append(facts)
            
        except Exception as e:
            logger.error(f"Error chunking {doc['scheme_name']}: {str(e)}")

    before = len(all_chunks)
    all_chunks = _dedupe_chunks(all_chunks)
    logger.info("Deduped chunks: %s -> %s", before, len(all_chunks))
    
    # Save chunks to JSON
    output_file = os.path.join(processed_dir, 'chunked_data_phase1.4.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_chunks, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Chunked data saved to: {output_file}")
    logger.info(f"Total chunks created: {len(all_chunks)}")
    logger.info(f"Phase 1.4 Chunker complete!")


if __name__ == "__main__":
    main()
