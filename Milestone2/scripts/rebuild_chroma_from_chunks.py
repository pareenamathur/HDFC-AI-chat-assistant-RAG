#!/usr/bin/env python3
"""
Rebuild Chroma `mf_faq_corpus` from data/processed/chunked_data_phase1.4.json
using all-MiniLM-L6-v2 (same as HybridRetriever).

Usage (from Milestone2/):
  python scripts/rebuild_chroma_from_chunks.py
  python scripts/rebuild_chroma_from_chunks.py --force

Cross-platform: uses relative paths only in metadata (basename for file-like fields).
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List

os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")
logger = logging.getLogger("rebuild_chroma")


def milestone2_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _basename_only(val: Any) -> str:
    s = str(val or "")
    if not s:
        return ""
    s = s.replace("\\", "/")
    return Path(s).name if "/" in s or "\\" in str(val) else s


def chunk_to_metadata(chunk: Dict[str, Any]) -> Dict[str, Any]:
    """Flatten to Chroma-allowed types only; no absolute paths."""
    meta: Dict[str, Any] = {}
    md = chunk.get("metadata") or {}
    meta["scheme_name"] = str(chunk.get("scheme_name") or md.get("scheme_name") or "")[:2048]
    meta["section"] = str(chunk.get("section") or "general")[:256]
    meta["source_document_id"] = str(chunk.get("source_document_id") or "")[:256]
    meta["document_type"] = str(md.get("document_type") or "")[:128]
    raw_url = str(md.get("page_url") or md.get("source_url") or "")
    if raw_url.startswith("http://") or raw_url.startswith("https://"):
        meta["source_url"] = raw_url[:512]
        meta["page_url"] = raw_url[:512]
    else:
        meta["source_url"] = _basename_only(raw_url)[:512]
    if md.get("nav_as_of"):
        meta["nav_as_of"] = str(md.get("nav_as_of"))[:32]
    meta["category"] = str(md.get("category") or "")[:256]
    sd = chunk.get("structured_data") or {}
    for k in ("expense_ratio", "exit_load", "nav", "aum", "sip_minimum", "risk_level", "nav_as_of"):
        val = md.get(k) if md.get(k) is not None else sd.get(k)
        if val is not None:
            meta[k] = str(val)[:256]
    if md.get("chunk_number") is not None:
        try:
            meta["chunk_number"] = int(md["chunk_number"])
        except (TypeError, ValueError):
            meta["chunk_number"] = 0
    if md.get("chunk_length") is not None:
        try:
            meta["chunk_length"] = int(md["chunk_length"])
        except (TypeError, ValueError):
            meta["chunk_length"] = 0
    meta["embedding_model"] = "sentence-transformers/all-MiniLM-L6-v2"
    return meta


def clear_index_dir(indexed: Path, force: bool) -> None:
    if not force and any(indexed.iterdir()) and (indexed / "chroma.sqlite3").exists():
        logger.info("Index exists; use --force to wipe non-README files.")
    if not indexed.exists():
        indexed.mkdir(parents=True, exist_ok=True)
    for child in list(indexed.iterdir()):
        if child.name == "README.md":
            continue
        if child.is_dir():
            shutil.rmtree(child, ignore_errors=True)
        else:
            try:
                child.unlink()
            except OSError:
                pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="Delete existing Chroma files (keeps README.md)")
    ap.add_argument("--batch-size", type=int, default=64)
    args = ap.parse_args()

    root = milestone2_root()
    chunked_path = root / "data" / "processed" / "chunked_data_phase1.4.json"
    indexed = root / "data" / "indexed"

    if not chunked_path.is_file():
        logger.error("Missing %s — cannot rebuild.", chunked_path)
        return 1

    indexed.mkdir(parents=True, exist_ok=True)
    if args.force or not (indexed / "chroma.sqlite3").is_file():
        clear_index_dir(indexed, force=True)
    else:
        logger.info("Leaving existing index (no --force). Exiting.")
        return 0

    with open(chunked_path, encoding="utf-8") as f:
        chunks: List[Dict[str, Any]] = json.load(f)
    if not isinstance(chunks, list) or not chunks:
        logger.error("chunked JSON is empty or not a list.")
        return 1

    logger.info("Loaded %s chunks from %s", len(chunks), chunked_path)

    import chromadb
    from sentence_transformers import SentenceTransformer

    model_name = "all-MiniLM-L6-v2"
    logger.info("Loading embedding model %s …", model_name)
    model = SentenceTransformer(model_name)

    client = chromadb.PersistentClient(path=str(indexed))
    try:
        client.delete_collection("mf_faq_corpus")
        logger.info("Deleted existing collection mf_faq_corpus")
    except Exception:
        pass

    collection = client.create_collection(
        name="mf_faq_corpus",
        metadata={
            "hnsw:space": "cosine",
            "embedding_model": model_name,
        },
    )

    batch = max(8, min(args.batch_size, 256))
    total = 0
    for start in range(0, len(chunks), batch):
        sub = chunks[start : start + batch]
        ids = [str(c.get("chunk_id") or f"chunk_{start + i}") for i, c in enumerate(sub)]
        docs = [str(c.get("text") or "")[:32000] for c in sub]
        metas = [chunk_to_metadata(c) for c in sub]
        emb = model.encode(
            docs,
            convert_to_numpy=True,
            show_progress_bar=False,
            batch_size=min(batch, 32),
        ).tolist()
        collection.add(ids=ids, embeddings=emb, documents=docs, metadatas=metas)
        total += len(sub)
        logger.info("Indexed batch %s–%s (%s total)", start, start + len(sub) - 1, total)

    n = collection.count()
    logger.info("Chroma collection mf_faq_corpus count=%s", n)

    # Validation query
    q = "What is the expense ratio for HDFC Balanced Advantage Fund?"
    qe = model.encode([q], convert_to_numpy=True, show_progress_bar=False).tolist()
    res = collection.query(query_embeddings=qe, n_results=2, include=["documents", "distances", "metadatas"])
    logger.info("Smoke query top distance: %s", res["distances"][0][0] if res.get("distances") else "n/a")

    logger.info("RAG index rebuild complete under %s", indexed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
