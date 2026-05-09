"""
Run Phase 1.5 - Embedder
Reads chunked data from Phase 1.4, generates embeddings, validates, and saves.
"""

import sys
import os
import json
import logging
import time
from datetime import datetime
from pathlib import Path

# Disable logging to avoid PowerShell output issues
logging.disable(logging.CRITICAL)

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from embedder import Embedder, EmbeddedChunk


def load_chunked_data(input_path: str) -> list:
    """Load chunked data from Phase 1.4 JSON."""
    with open(input_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_embedded_data(embedded_chunks: list, output_path: str):
    """Save embedded data to JSON."""
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(embedded_chunks, f, ensure_ascii=False, indent=2)


def run_phase_1_5():
    """Main entry point for Phase 1.5 execution."""
    # Resolve paths
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent.parent
    input_path = project_root / "data" / "processed" / "chunked_data_phase1.4.json"
    output_path = project_root / "data" / "processed" / "embedded_data_phase1.5.json"
    log_path = project_root / "phase1.5_run.log"

    # Log file for output (avoids PowerShell display issues)
    log_file = open(log_path, "w", encoding="utf-8")
    def log(msg):
        log_file.write(msg + "\n")
        log_file.flush()

    log(f"{'='*60}")
    log(f"Phase 1.5 - Embedder Run")
    log(f"Started: {datetime.now().isoformat()}")
    log(f"{'='*60}")

    # Load chunked data
    if not input_path.exists():
        log(f"ERROR: Input file not found: {input_path}")
        log_file.close()
        return

    chunks = load_chunked_data(str(input_path))
    log(f"Loaded {len(chunks)} chunks from {input_path.name}")

    # Show chunk stats
    scheme_names = set()
    for c in chunks:
        sn = c.get("scheme_name", c.get("metadata", {}).get("scheme_name", "Unknown"))
        scheme_names.add(sn)
    log(f"Unique schemes: {len(scheme_names)}")
    for sn in sorted(scheme_names):
        count = sum(1 for c in chunks if c.get("scheme_name", c.get("metadata", {}).get("scheme_name", "")) == sn)
        log(f"  - {sn}: {count} chunks")

    # Initialize embedder
    log(f"\nInitializing embedder with model: BAAI/bge-small-en-v1.5")
    embedder = Embedder(
        model_name="BAAI/bge-small-en-v1.5",
        batch_size=64,
        enrich_with_structured_data=True,
        normalize_embeddings=True,
    )

    # Generate embeddings
    log(f"\nGenerating embeddings (batch_size=64, enrich_with_structured_data=True)...")
    start_time = time.time()
    embedded_chunks = embedder.embed_chunks(chunks)
    elapsed = time.time() - start_time
    log(f"Embedding completed in {elapsed:.1f}s ({len(embedded_chunks)} chunks, {elapsed/len(embedded_chunks):.3f}s/chunk)")

    # Validate embeddings
    log(f"\nValidating embeddings...")
    report = embedder.validate_embeddings(embedded_chunks)
    log(f"Validation Report:")
    log(f"  Total chunks: {report['total_chunks']}")
    log(f"  Valid chunks: {report['valid_count']}")
    log(f"  Dimension mismatches: {report['dimension_mismatches']}")
    log(f"  Zero-norm embeddings: {report['zero_norm_count']}")
    log(f"  NaN/Inf values: {report['nan_inf_count']}")
    log(f"  Missing metadata: {report['missing_metadata_count']}")
    log(f"  Dimension distribution: {report['dimension_distribution']}")
    log(f"  Overall valid: {report['is_valid']}")

    if report["errors"]:
        log(f"\nFirst 5 errors:")
        for err in report["errors"][:5]:
            log(f"  - {err}")

    # Quick similarity sanity check
    log(f"\nSimilarity sanity check:")
    if len(embedded_chunks) >= 2:
        sim_same_doc = []
        sim_diff_doc = []
        doc_ids = set(ec.source_document_id for ec in embedded_chunks)

        # Compare a few pairs from same document
        for doc_id in list(doc_ids)[:3]:
            doc_chunks = [ec for ec in embedded_chunks if ec.source_document_id == doc_id]
            if len(doc_chunks) >= 2:
                sim = embedder.compute_similarity(doc_chunks[0].embedding, doc_chunks[1].embedding)
                sim_same_doc.append(sim)
                log(f"  Same-doc ({doc_id[:20]}...): cos_sim={sim:.4f}")

        # Compare pairs from different documents
        doc_list = list(doc_ids)
        if len(doc_list) >= 2:
            ec1 = [ec for ec in embedded_chunks if ec.source_document_id == doc_list[0]][0]
            ec2 = [ec for ec in embedded_chunks if ec.source_document_id == doc_list[1]][0]
            sim = embedder.compute_similarity(ec1.embedding, ec2.embedding)
            sim_diff_doc.append(sim)
            log(f"  Diff-doc ({doc_list[0][:15]}... vs {doc_list[1][:15]}...): cos_sim={sim:.4f}")

        if sim_same_doc:
            log(f"  Avg same-doc similarity: {sum(sim_same_doc)/len(sim_same_doc):.4f}")
        if sim_diff_doc:
            log(f"  Avg diff-doc similarity: {sum(sim_diff_doc)/len(sim_diff_doc):.4f}")

    # Save embedded data
    log(f"\nSaving embedded data to {output_path.name}...")
    serializable = embedder.to_serializable(embedded_chunks)
    save_embedded_data(serializable, str(output_path))

    file_size_mb = output_path.stat().st_size / (1024 * 1024)
    log(f"Saved {len(serializable)} embedded chunks ({file_size_mb:.1f} MB)")

    # Final summary
    log(f"\n{'='*60}")
    log(f"Phase 1.5 Complete")
    log(f"  Chunks processed: {len(embedded_chunks)}")
    log(f"  Embedding model: BAAI/bge-small-en-v1.5")
    log(f"  Embedding dimensions: {report['expected_dimensions']}")
    log(f"  Validation: {'PASSED' if report['is_valid'] else 'FAILED'}")
    log(f"  Output: {output_path}")
    log(f"  Elapsed: {elapsed:.1f}s")
    log(f"{'='*60}")

    log_file.close()
    print(f"Phase 1.5 complete. See {log_path} for details.")


if __name__ == "__main__":
    run_phase_1_5()
