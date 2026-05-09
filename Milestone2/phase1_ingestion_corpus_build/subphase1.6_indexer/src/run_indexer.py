"""
Run Phase 1.6 - Indexer
Reads embedded data from Phase 1.5, indexes into ChromaDB with persistence,
validates the index, and runs a test query.
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

from indexer import Indexer


def load_embedded_data(input_path: str) -> list:
    """Load embedded data from Phase 1.5 JSON."""
    with open(input_path, "r", encoding="utf-8") as f:
        return json.load(f)


def run_phase_1_6():
    """Main entry point for Phase 1.6 execution."""
    # Resolve paths
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent.parent
    input_path = project_root / "data" / "processed" / "embedded_data_phase1.5.json"
    chroma_dir = project_root / "data" / "indexed"
    log_path = project_root / "phase1.6_run.log"

    # Log file for output (avoids PowerShell display issues)
    log_file = open(log_path, "w", encoding="utf-8")
    def log(msg):
        log_file.write(msg + "\n")
        log_file.flush()

    log(f"{'='*60}")
    log(f"Phase 1.6 - Indexer Run")
    log(f"Started: {datetime.now().isoformat()}")
    log(f"{'='*60}")

    # Load embedded data
    if not input_path.exists():
        log(f"ERROR: Input file not found: {input_path}")
        log_file.close()
        return

    chunks = load_embedded_data(str(input_path))
    log(f"Loaded {len(chunks)} embedded chunks from {input_path.name}")

    # Verify all chunks have embeddings
    missing_embeddings = sum(1 for c in chunks if not c.get("embedding"))
    if missing_embeddings > 0:
        log(f"WARNING: {missing_embeddings} chunks missing embeddings - they will be skipped")
    
    embedding_dims = set()
    for c in chunks:
        if c.get("embedding"):
            embedding_dims.add(len(c["embedding"]))
    log(f"Embedding dimensions found: {embedding_dims}")

    # Initialize indexer
    log(f"\nInitializing ChromaDB indexer...")
    log(f"  Persist directory: {chroma_dir}")
    log(f"  Collection name: mf_faq_corpus")
    log(f"  Embedding model: BAAI/bge-small-en-v1.5")

    indexer = Indexer(
        persist_directory=str(chroma_dir),
        collection_name="mf_faq_corpus",
        embedding_model_name="BAAI/bge-small-en-v1.5",
    )

    # Index chunks
    log(f"\nIndexing {len(chunks)} chunks into ChromaDB...")
    start_time = time.time()
    report = indexer.index_chunks(chunks, batch_size=500)
    elapsed = time.time() - start_time

    log(f"\nIndexing Report:")
    log(f"  Total input chunks: {report['total_input_chunks']}")
    log(f"  Indexed (new): {report['indexed_count']}")
    log(f"  Skipped (existing): {report['skipped_count']}")
    log(f"  Errors: {report['error_count']}")
    log(f"  Batches processed: {report['batch_count']}")
    log(f"  Total in collection: {report['total_in_collection']}")
    log(f"  Elapsed: {report['elapsed_seconds']}s")

    if report["errors"]:
        log(f"\nFirst 5 errors:")
        for err in report["errors"][:5]:
            log(f"  - {err}")

    # Get collection stats
    log(f"\nCollection Statistics:")
    stats = indexer.get_collection_stats()
    log(f"  Collection name: {stats['collection_name']}")
    log(f"  Total chunks: {stats['total_chunks']}")
    log(f"  Embedding model: {stats['embedding_model']}")
    if "unique_schemes" in stats:
        log(f"  Unique schemes: {stats['unique_schemes']}")
        log(f"\n  Scheme distribution:")
        for scheme, count in sorted(stats.get("scheme_counts", {}).items()):
            log(f"    - {scheme}: {count} chunks")
        log(f"\n  Category distribution:")
        for cat, count in sorted(stats.get("category_counts", {}).items()):
            log(f"    - {cat}: {count} chunks")

    # Validate index
    log(f"\nValidating index...")
    validation = indexer.validate_index()
    log(f"Validation Report:")
    log(f"  Overall valid: {validation['is_valid']}")
    for check, result in validation["checks"].items():
        status = "PASS" if result else "FAIL"
        log(f"  - {check}: {status}")
    if validation["errors"]:
        for err in validation["errors"]:
            log(f"  ERROR: {err}")

    # Run test queries to verify retrieval quality
    log(f"\n{'='*60}")
    log(f"Test Queries (verifying retrieval quality):")
    log(f"{'='*60}")

    test_queries = [
        "What is the expense ratio of HDFC Balanced Advantage Fund?",
        "What is the exit load for HDFC Flexi Cap Fund?",
        "What is the risk level of HDFC Small Cap Fund?",
        "Tell me about HDFC Gold ETF Fund",
        "What is the NAV of HDFC Nifty 50 Index Fund?",
    ]

    for query in test_queries:
        log(f"\nQuery: '{query}'")
        try:
            results = indexer.query_by_text(query, n_results=3)
            for i, (doc_id, distance, metadata) in enumerate(
                zip(results["ids"][0], results["distances"][0], results["metadatas"][0])
            ):
                similarity = 1 - distance  # cosine similarity = 1 - cosine distance
                scheme = metadata.get("scheme_name", "Unknown")[:50]
                log(f"  Result {i+1}: sim={similarity:.4f} | {scheme}... | {doc_id}")
        except Exception as e:
            log(f"  Query error: {str(e)}")

    # Test metadata filtering
    log(f"\n{'='*60}")
    log(f"Metadata Filtering Test:")
    log(f"{'='*60}")

    try:
        # Query with scheme_name filter
        filter_query = "expense ratio"
        log(f"\nFiltered query: '{filter_query}' (scheme_name contains 'HDFC Corporate Bond')")
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
        ef = SentenceTransformerEmbeddingFunction(model_name="BAAI/bge-small-en-v1.5")
        q_emb = ef([filter_query])[0]
        
        # Get all scheme names to find one for filtering
        all_data = indexer._get_or_create_collection().get(limit=5, include=["metadatas"])
        if all_data["metadatas"]:
            sample_scheme = all_data["metadatas"][0].get("scheme_name", "")
            if sample_scheme:
                filtered_results = indexer.query(
                    q_emb, n_results=3,
                    where={"scheme_name": sample_scheme}
                )
                log(f"  Filter: scheme_name = '{sample_scheme[:50]}...'")
                for i, (doc_id, distance, meta) in enumerate(
                    zip(filtered_results["ids"][0], filtered_results["distances"][0], filtered_results["metadatas"][0])
                ):
                    sim = 1 - distance
                    log(f"  Result {i+1}: sim={sim:.4f} | scheme={meta.get('scheme_name', '?')[:50]}...")
    except Exception as e:
        log(f"  Filter test error: {str(e)}")

    # Final summary
    log(f"\n{'='*60}")
    log(f"Phase 1.6 Complete")
    log(f"  Chunks indexed: {report['indexed_count']}")
    log(f"  Total in collection: {report['total_in_collection']}")
    log(f"  ChromaDB path: {chroma_dir}")
    log(f"  Validation: {'PASSED' if validation['is_valid'] else 'FAILED'}")
    log(f"  Elapsed: {elapsed:.1f}s")
    log(f"{'='*60}")

    log_file.close()
    print(f"Phase 1.6 complete. See {log_path} for details.")


if __name__ == "__main__":
    run_phase_1_6()
