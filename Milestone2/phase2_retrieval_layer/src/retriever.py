import os
import logging
from typing import List, Dict, Any, Optional
import chromadb
from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

logger = logging.getLogger(__name__)

class HybridRetriever:
    """Handles hybrid retrieval (Vector + BM25) and reranking."""

    def __init__(
        self,
        persist_directory: str,
        collection_name: str = "mf_faq_corpus",
        embedding_model_name: str = "BAAI/bge-small-en-v1.5",
        reranker_model_name: str = "BAAI/bge-reranker-base",
        vector_weight: float = 0.7,
        bm25_weight: float = 0.3
    ):
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        self.embedding_model_name = embedding_model_name
        self.reranker_model_name = reranker_model_name
        self.vector_weight = vector_weight
        self.bm25_weight = bm25_weight

        # Initialize ChromaDB
        self.client = chromadb.PersistentClient(path=persist_directory)
        self.collection = self.client.get_collection(name=collection_name)
        
        # Initialize Embedding Model for manual embedding generation
        from sentence_transformers import SentenceTransformer
        self.embedding_model = SentenceTransformer(embedding_model_name)

        # Initialize Reranker
        logger.info(f"Loading reranker: {reranker_model_name}")
        self.reranker = CrossEncoder(reranker_model_name)

        # Initialize BM25
        self._initialize_bm25()

    def _initialize_bm25(self):
        """Builds BM25 index from all chunks in the collection."""
        logger.info("Initializing BM25 index...")
        all_data = self.collection.get(include=["documents", "metadatas"])
        self.all_ids = all_data["ids"]
        self.all_documents = all_data["documents"]
        self.all_metadatas = all_data["metadatas"]

        tokenized_corpus = [doc.lower().split() for doc in self.all_documents]
        self.bm25 = BM25Okapi(tokenized_corpus)
        logger.info(f"BM25 initialized with {len(self.all_ids)} chunks.")

    def search(
        self,
        query: str,
        n_results: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        top_k_hybrid: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Performs hybrid search and returns reranked results.
        
        Args:
            query: User query string
            n_results: Final number of results to return
            filters: Metadata filters for ChromaDB
            top_k_hybrid: Number of candidates to retrieve for reranking
        """
        # Generate embedding manually
        query_embedding = self.embedding_model.encode(query).tolist()

        # Handle empty filters
        if filters == {}:
            filters = None

        # 1. Vector Search
        vector_results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k_hybrid,
            where=filters,
            include=["documents", "metadatas", "distances"]
        )

        # Flatten vector results
        vector_hits = []
        if vector_results["ids"]:
            for i in range(len(vector_results["ids"][0])):
                vector_hits.append({
                    "id": vector_results["ids"][0][i],
                    "text": vector_results["documents"][0][i],
                    "metadata": vector_results["metadatas"][0][i],
                    "score": 1 - vector_results["distances"][0][i] # Normalize to 0-1
                })

        # 2. BM25 Search
        tokenized_query = query.lower().split()
        bm25_scores = self.bm25.get_scores(tokenized_query)
        
        # Normalize BM25 scores (simple max normalization)
        max_bm25 = max(bm25_scores) if len(bm25_scores) > 0 and max(bm25_scores) > 0 else 1
        
        # Combine results
        combined_results = {}
        
        # Start with vector hits
        for hit in vector_hits:
            combined_results[hit["id"]] = hit
            combined_results[hit["id"]]["hybrid_score"] = hit["score"] * self.vector_weight

        # Add BM25 scores to combined results (if the ID exists in filtered vector hits or if no filters)
        # For simplicity, we'll just score the vector hits using BM25
        for hit_id, hit in combined_results.items():
            # Find index in full corpus
            try:
                idx = self.all_ids.index(hit_id)
                bm25_score = bm25_scores[idx] / max_bm25
                hit["hybrid_score"] += bm25_score * self.bm25_weight
            except ValueError:
                continue

        # 3. Reranking
        candidates = sorted(combined_results.values(), key=lambda x: x["hybrid_score"], reverse=True)[:top_k_hybrid]
        
        if not candidates:
            return []

        # Prepare pairs for cross-encoder
        pairs = [[query, c["text"]] for c in candidates]
        rerank_scores = self.reranker.predict(pairs)

        for i, candidate in enumerate(candidates):
            candidate["rerank_score"] = float(rerank_scores[i])

        # Sort by rerank score
        final_results = sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)[:n_results]
        
        return final_results

if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.INFO)
    retriever = HybridRetriever(
        persist_directory="data/indexed",
        collection_name="mf_faq_corpus"
    )
    
    results = retriever.search("What is the exit load for HDFC Balanced Advantage Fund?", n_results=3)
    for r in results:
        print(f"Score: {r['rerank_score']:.4f} | Text: {r['text'][:100]}...")
