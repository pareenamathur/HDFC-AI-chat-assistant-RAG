import os
import gc
import logging
import time
from typing import List, Dict, Any, Optional

import chromadb

logger = logging.getLogger(__name__)


def get_memory_usage():
    """Get current memory usage in MB."""
    try:
        import psutil
        process = psutil.Process()
        memory_info = process.memory_info()
        return memory_info.rss / 1024 / 1024
    except ImportError:
        return None


class HybridRetriever:
    """Hybrid retrieval (Vector + optional BM25 + optional rerank). Cloud profile uses vector-only."""

    def __init__(
        self,
        persist_directory: str,
        collection_name: str = "mf_faq_corpus",
        embedding_model_name: str = "all-MiniLM-L6-v2",
        reranker_model_name: str = "BAAI/bge-reranker-base",
        vector_weight: float = 0.7,
        bm25_weight: float = 0.3,
        use_bm25: bool = False,
        use_reranker: bool = False,
        vector_fetch_k: int = 12,
    ):
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        self.embedding_model_name = embedding_model_name
        self.reranker_model_name = reranker_model_name
        self.vector_weight = vector_weight
        self.bm25_weight = bm25_weight
        self.use_bm25 = use_bm25
        self.use_reranker = use_reranker
        self.vector_fetch_k = max(4, min(vector_fetch_k, 24))

        self.embedding_model = None
        self.reranker = None
        self.bm25 = None
        self.all_ids: List = []
        self.all_documents: List = []

        logger.info("Initializing ChromaDB client (on-disk, lazy query execution)")
        self.client = chromadb.PersistentClient(path=persist_directory)
        self.collection = self.client.get_collection(name=collection_name)
        try:
            _n = self.collection.count()
            logger.info(
                'Chroma collection opened — name="%s" document_count=%s path=%s',
                collection_name,
                _n,
                persist_directory,
            )
        except Exception as e:
            logger.warning("Chroma collection opened but count() failed: %s", e)

        if use_reranker:
            from sentence_transformers import CrossEncoder
            logger.info("Loading reranker: %s", reranker_model_name)
            self.reranker = CrossEncoder(reranker_model_name)
        else:
            logger.info("Reranker disabled (memory profile)")

        if use_bm25:
            self._initialize_bm25()
        else:
            logger.info("BM25 disabled (memory profile)")

        gc.collect()

    def _ensure_embedding_model(self):
        """Lazy-load MiniLM once; avoids duplicate loads if retriever reinstantiated elsewhere."""
        if self.embedding_model is None:
            before = get_memory_usage()
            logger.info("Lazy-loading embedding model: %s (before ~%.1f MB)", self.embedding_model_name, before or -1)
            from sentence_transformers import SentenceTransformer
            self.embedding_model = SentenceTransformer(self.embedding_model_name)
            after = get_memory_usage()
            logger.info(
                "Embedding model initialized: %s (after ~%.1f MB)",
                self.embedding_model_name,
                after or -1,
            )
            gc.collect()
        return self.embedding_model

    def fetch_chunks_matching_text(
        self,
        scheme_name: str,
        substring: str,
        limit: int = 3,
    ) -> List[Dict[str, Any]]:
        """Metadata-filtered scan for chunks containing a literal substring (e.g. Holdings table)."""
        try:
            data = self.collection.get(
                where={"scheme_name": scheme_name},
                include=["documents", "metadatas"],
            )
        except Exception as e:
            logger.warning("fetch_chunks_matching_text failed: %s", e)
            return []
        ids = data.get("ids") or []
        docs = data.get("documents") or []
        metas = data.get("metadatas") or []
        hits: List[Dict[str, Any]] = []
        needle = (substring or "").lower()
        for i, cid in enumerate(ids):
            doc = (docs[i] if i < len(docs) else "") or ""
            if needle and needle not in doc.lower():
                continue
            meta = metas[i] if i < len(metas) and isinstance(metas[i], dict) else {}
            hits.append(
                {
                    "id": cid,
                    "text": doc,
                    "metadata": meta,
                    "score": 0.99,
                    "score_adjusted": 0.99,
                    "source": "metadata_scan",
                }
            )
            if len(hits) >= limit:
                break
        return hits

    def warm_vector_pipeline(self, probe_query: str = "HDFC mutual fund overview") -> None:
        """Load MiniLM and run one minimal Chroma query (same thread as caller; for /health readiness)."""
        _ = self.search(probe_query, n_results=1, filters=None)
        logger.info("Embedding test successful (probe query: encode + Chroma query completed).")

    def _initialize_bm25(self):
        """Load full document texts for BM25 — memory-heavy; only when use_bm25=True."""
        from rank_bm25 import BM25Okapi
        logger.info("Initializing BM25 index (loading document ids from collection)")
        all_data = self.collection.get(include=["documents", "metadatas"])
        self.all_ids = all_data["ids"]
        self.all_documents = all_data["documents"]
        self.all_metadatas = all_data["metadatas"]
        tokenized_corpus = [doc.lower().split() for doc in self.all_documents]
        self.bm25 = BM25Okapi(tokenized_corpus)
        logger.info("BM25 initialized with %s chunks.", len(self.all_ids))
        gc.collect()

    def search(
        self,
        query: str,
        n_results: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        top_k_hybrid: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Vector-first retrieval; optional BM25 fusion and CrossEncoder rerank."""
        t_wall = time.perf_counter()
        q_preview = (query or "")[:160]
        logger.info(
            "retriever.search START model=%s n_results=%s fetch_k=%s where=%s query_preview=%r",
            self.embedding_model_name,
            n_results,
            top_k_hybrid if top_k_hybrid is not None else self.vector_fetch_k,
            filters,
            q_preview,
        )

        t0 = time.perf_counter()
        model = self._ensure_embedding_model()
        query_embedding = model.encode(
            query,
            convert_to_numpy=True,
            show_progress_bar=False,
            batch_size=1,
        ).tolist()
        emb_dim = len(query_embedding) if isinstance(query_embedding, list) else -1
        logger.info(
            "retriever.search STAGE=encode OK ms=%.1f embedding_dim=%s",
            (time.perf_counter() - t0) * 1000,
            emb_dim,
        )

        if filters == {}:
            filters = None

        fetch_k = top_k_hybrid if top_k_hybrid is not None else self.vector_fetch_k
        if self.use_reranker and self.reranker:
            fetch_k = min(max(fetch_k, n_results), 50)

        t0 = time.perf_counter()
        try:
            vector_results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=fetch_k,
                where=filters,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as e:
            err = str(e).lower()
            logger.exception(
                "retriever.search STAGE=chroma_query FAILED ms=%.1f embedding_dim=%s where=%s err_type=%s",
                (time.perf_counter() - t0) * 1000,
                emb_dim,
                filters,
                type(e).__name__,
            )
            if "dimension" in err or "embedding" in err:
                logger.error(
                    "Possible embedding dimension mismatch vs index. "
                    "Rebuild with: python scripts/rebuild_chroma_from_chunks.py --force "
                    "(index must use same model as HybridRetriever: %s).",
                    self.embedding_model_name,
                )
            raise

        logger.info(
            "retriever.search STAGE=chroma_query OK ms=%.1f",
            (time.perf_counter() - t0) * 1000,
        )

        vector_hits = []
        ids_outer = vector_results.get("ids") or []
        if ids_outer and ids_outer[0]:
            row_ids = ids_outer[0]
            docs_row = (vector_results.get("documents") or [[]])[0] or []
            metas_row = (vector_results.get("metadatas") or [[]])[0] or []
            dist_row = (vector_results.get("distances") or [[]])[0] or []
            n = len(row_ids)
            for i in range(n):
                doc_i = docs_row[i] if i < len(docs_row) else None
                meta_i = metas_row[i] if i < len(metas_row) else None
                dist_i = dist_row[i] if i < len(dist_row) else 1.0
                try:
                    score = 1.0 - float(dist_i)
                except (TypeError, ValueError):
                    score = 0.0
                vector_hits.append({
                    "id": row_ids[i],
                    "text": (doc_i if doc_i is not None else "") or "",
                    "metadata": meta_i if isinstance(meta_i, dict) else {},
                    "score": score,
                })

        if self.use_bm25 and self.bm25:
            tokenized_query = query.lower().split()
            bm25_scores = self.bm25.get_scores(tokenized_query)
            max_bm25 = max(bm25_scores) if bm25_scores and max(bm25_scores) > 0 else 1
            combined_results: Dict[str, Dict[str, Any]] = {}
            for hit in vector_hits:
                combined_results[hit["id"]] = hit
                combined_results[hit["id"]]["hybrid_score"] = hit["score"] * self.vector_weight
            for hit_id, hit in combined_results.items():
                try:
                    idx = self.all_ids.index(hit_id)
                    bm25_score = bm25_scores[idx] / max_bm25
                    hit["hybrid_score"] += bm25_score * self.bm25_weight
                except ValueError:
                    continue
            candidates = sorted(
                combined_results.values(),
                key=lambda x: x["hybrid_score"],
                reverse=True,
            )[:fetch_k]
        else:
            candidates = vector_hits[:fetch_k]

        if not candidates:
            logger.info(
                "retriever.search END hits_out=0 total_ms=%.1f (no vector hits after query)",
                (time.perf_counter() - t_wall) * 1000,
            )
            return []

        if self.use_reranker and self.reranker:
            t0 = time.perf_counter()
            pairs = [[query, c["text"]] for c in candidates]
            rerank_scores = self.reranker.predict(pairs)
            logger.info(
                "retriever.search STAGE=rerank OK ms=%.1f candidates=%s",
                (time.perf_counter() - t0) * 1000,
                len(candidates),
            )
            for i, candidate in enumerate(candidates):
                candidate["rerank_score"] = float(rerank_scores[i])
            final_results = sorted(
                candidates,
                key=lambda x: x["rerank_score"],
                reverse=True,
            )[:n_results]
        else:
            if self.use_bm25:
                final_results = sorted(
                    candidates,
                    key=lambda x: x["hybrid_score"],
                    reverse=True,
                )[:n_results]
            else:
                final_results = sorted(
                    candidates,
                    key=lambda x: x["score"],
                    reverse=True,
                )[:n_results]

        gc.collect()
        logger.info(
            "retriever.search END hits_out=%s total_ms=%.1f reranker=%s bm25=%s",
            len(final_results),
            (time.perf_counter() - t_wall) * 1000,
            bool(self.use_reranker and self.reranker),
            bool(self.use_bm25 and self.bm25),
        )
        return final_results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    retriever = HybridRetriever(
        persist_directory="data/indexed",
        collection_name="mf_faq_corpus",
        use_bm25=False,
        use_reranker=False,
    )
    results = retriever.search(
        "What is the exit load for HDFC Balanced Advantage Fund?",
        n_results=3,
    )
    for r in results:
        print(f"Score: {r.get('score', r.get('hybrid_score', 0)):.4f} | Text: {r['text'][:100]}...")
