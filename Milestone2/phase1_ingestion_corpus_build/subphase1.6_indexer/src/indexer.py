"""
Indexer Module - Phase 1.6
Ingests embedded chunks into ChromaDB with local persistence and metadata indexing.
"""

from typing import Dict, List, Optional, Any
import logging
import time
from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings

logger = logging.getLogger(__name__)


class Indexer:
    """Indexes embedded chunks into ChromaDB with persistence and metadata filtering."""

    def __init__(
        self,
        persist_directory: str = "./chroma_db",
        collection_name: str = "mf_faq_corpus",
        embedding_model_name: str = "BAAI/bge-small-en-v1.5",
    ):
        """
        Initialize the indexer.

        Args:
            persist_directory: Local directory for ChromaDB persistence
            collection_name: Name of the ChromaDB collection
            embedding_model_name: Name of the embedding model (for metadata tracking)
        """
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        self.embedding_model_name = embedding_model_name
        self._client = None
        self._collection = None

    def _get_client(self) -> chromadb.PersistentClient:
        """Get or create a persistent ChromaDB client."""
        if self._client is None:
            logger.info(f"Initializing ChromaDB client at: {self.persist_directory}")
            self._client = chromadb.PersistentClient(path=self.persist_directory)
        return self._client

    def _get_or_create_collection(self) -> chromadb.Collection:
        """Get or create the ChromaDB collection with metadata schema."""
        if self._collection is None:
            client = self._get_client()
            logger.info(f"Getting/creating collection: {self.collection_name}")
            self._collection = client.get_or_create_collection(
                name=self.collection_name,
                metadata={
                    "hnsw:space": "cosine",
                    "description": "HDFC Mutual Fund FAQ corpus - facts-only RAG",
                    "embedding_model": self.embedding_model_name,
                },
            )
            logger.info(f"Collection ready. Current count: {self._collection.count()}")
        return self._collection

    def _prepare_metadata(self, chunk: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare metadata for ChromaDB ingestion.
        
        ChromaDB requires metadata values to be str, int, float, or bool.
        Flatten nested structures and convert types accordingly.

        Args:
            chunk: Embedded chunk dictionary from Phase 1.5

        Returns:
            Flat metadata dict compatible with ChromaDB
        """
        metadata = {}

        # Core fields from the chunk
        metadata["section"] = str(chunk.get("section", "general"))
        metadata["source_document_id"] = str(chunk.get("source_document_id", ""))
        metadata["scheme_name"] = str(chunk.get("scheme_name", ""))
        metadata["embedding_model"] = str(chunk.get("embedding_model", ""))
        metadata["embedding_dimensions"] = int(chunk.get("embedding_dimensions", 384))

        # Flatten document metadata
        doc_metadata = chunk.get("metadata", {})
        if doc_metadata:
            metadata["document_type"] = str(doc_metadata.get("document_type", ""))
            metadata["source_url"] = str(doc_metadata.get("source_url", ""))
            metadata["category"] = str(doc_metadata.get("category", ""))
            metadata["content_length"] = int(doc_metadata.get("content_length", 0))
            metadata["chunk_number"] = int(doc_metadata.get("chunk_number", 0))
            metadata["chunk_length"] = int(doc_metadata.get("chunk_length", 0))

        # Flatten structured data with prefixed keys
        structured_data = chunk.get("structured_data", {})
        if structured_data:
            for key, value in structured_data.items():
                if value is not None:
                    metadata[f"sd_{key}"] = str(value)

        # Include document-level metadata fields
        for field in ["expense_ratio", "exit_load", "nav", "aum", "sip_minimum", "risk_level"]:
            if field in doc_metadata and doc_metadata[field]:
                metadata[field] = str(doc_metadata[field])

        return metadata

    def index_chunks(self, chunks: List[Dict[str, Any]], batch_size: int = 500) -> Dict[str, Any]:
        """
        Ingest embedded chunks into ChromaDB.

        Args:
            chunks: List of embedded chunk dicts from Phase 1.5
            batch_size: Number of chunks to index per batch (ChromaDB limit ~5000)

        Returns:
            Indexing report dictionary
        """
        collection = self._get_or_create_collection()
        start_time = time.time()

        report = {
            "total_input_chunks": len(chunks),
            "indexed_count": 0,
            "skipped_count": 0,
            "error_count": 0,
            "errors": [],
            "batch_count": 0,
        }

        # Check for existing chunks to avoid duplicates
        existing_ids = set()
        try:
            existing = collection.get(include=[])
            existing_ids = set(existing["ids"])
            logger.info(f"Found {len(existing_ids)} existing chunks in collection")
        except Exception:
            logger.info("No existing chunks found in collection")

        # Prepare data for indexing
        ids_to_add = []
        documents_to_add = []
        embeddings_to_add = []
        metadatas_to_add = []

        for chunk in chunks:
            chunk_id = chunk.get("chunk_id", "")
            
            # Skip if already indexed
            if chunk_id in existing_ids:
                report["skipped_count"] += 1
                continue

            # Validate required fields
            if not chunk.get("embedding"):
                report["error_count"] += 1
                report["errors"].append(f"Chunk {chunk_id}: missing embedding")
                continue

            if not chunk.get("text"):
                report["error_count"] += 1
                report["errors"].append(f"Chunk {chunk_id}: missing text")
                continue

            ids_to_add.append(chunk_id)
            documents_to_add.append(chunk["text"])
            embeddings_to_add.append(chunk["embedding"])
            metadatas_to_add.append(self._prepare_metadata(chunk))

        # Batch insert into ChromaDB
        total_to_add = len(ids_to_add)
        if total_to_add > 0:
            for i in range(0, total_to_add, batch_size):
                batch_ids = ids_to_add[i:i + batch_size]
                batch_docs = documents_to_add[i:i + batch_size]
                batch_embeds = embeddings_to_add[i:i + batch_size]
                batch_metas = metadatas_to_add[i:i + batch_size]

                batch_num = i // batch_size + 1
                total_batches = (total_to_add + batch_size - 1) // batch_size
                logger.info(f"Indexing batch {batch_num}/{total_batches} ({len(batch_ids)} chunks)")

                try:
                    collection.upsert(
                        ids=batch_ids,
                        documents=batch_docs,
                        embeddings=batch_embeds,
                        metadatas=batch_metas,
                    )
                    report["indexed_count"] += len(batch_ids)
                    report["batch_count"] += 1
                except Exception as e:
                    report["error_count"] += len(batch_ids)
                    report["errors"].append(f"Batch {batch_num} error: {str(e)}")
                    logger.error(f"Error indexing batch {batch_num}: {str(e)}")

        elapsed = time.time() - start_time
        report["elapsed_seconds"] = round(elapsed, 2)
        report["total_in_collection"] = collection.count()

        logger.info(
            f"Indexing complete: {report['indexed_count']} added, "
            f"{report['skipped_count']} skipped, {report['error_count']} errors, "
            f"total in collection: {report['total_in_collection']}"
        )

        return report

    def query(
        self,
        query_embedding: List[float],
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None,
        where_document: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Query the ChromaDB collection for similar chunks.

        Args:
            query_embedding: Query embedding vector
            n_results: Number of results to return
            where: Metadata filter (e.g., {"scheme_name": "HDFC Balanced Advantage Fund"})
            where_document: Document content filter

        Returns:
            Query results from ChromaDB
        """
        collection = self._get_or_create_collection()
        return collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where,
            where_document=where_document,
            include=["documents", "metadatas", "distances", "embeddings"],
        )

    def query_by_text(
        self,
        query_text: str,
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Query by text (generates embedding and queries).

        Args:
            query_text: Natural language query
            n_results: Number of results to return
            where: Metadata filter

        Returns:
            Query results from ChromaDB
        """
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
        ef = SentenceTransformerEmbeddingFunction(model_name=self.embedding_model_name)
        query_embedding = ef([query_text])[0]
        return self.query(query_embedding, n_results=n_results, where=where)

    def get_collection_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the indexed collection.

        Returns:
            Dictionary with collection statistics
        """
        collection = self._get_or_create_collection()
        total = collection.count()

        stats = {
            "collection_name": self.collection_name,
            "persist_directory": self.persist_directory,
            "total_chunks": total,
            "embedding_model": self.embedding_model_name,
        }

        if total > 0:
            # Get all metadata to compute stats
            all_data = collection.get(include=["metadatas"])
            metadatas = all_data["metadatas"]

            # Count by scheme_name
            scheme_counts = {}
            doc_type_counts = {}
            category_counts = {}
            for meta in metadatas:
                sn = meta.get("scheme_name", "Unknown")
                dt = meta.get("document_type", "Unknown")
                cat = meta.get("category", "Unknown")
                scheme_counts[sn] = scheme_counts.get(sn, 0) + 1
                doc_type_counts[dt] = doc_type_counts.get(dt, 0) + 1
                category_counts[cat] = category_counts.get(cat, 0) + 1

            stats["unique_schemes"] = len(scheme_counts)
            stats["scheme_counts"] = scheme_counts
            stats["document_type_counts"] = doc_type_counts
            stats["category_counts"] = category_counts

        return stats

    def validate_index(self) -> Dict[str, Any]:
        """
        Validate the indexed corpus for integrity.

        Checks:
        1. Collection is non-empty
        2. All chunks have embeddings
        3. Metadata fields are present
        4. Similarity search returns results

        Returns:
            Validation report dictionary
        """
        collection = self._get_or_create_collection()
        total = collection.count()

        report = {
            "collection_exists": True,
            "total_chunks": total,
            "is_valid": False,
            "errors": [],
            "checks": {},
        }

        # Check 1: Non-empty collection
        if total == 0:
            report["errors"].append("Collection is empty")
            report["checks"]["non_empty"] = False
        else:
            report["checks"]["non_empty"] = True

        if total > 0:
            # Check 2: Sample chunks have proper metadata
            sample = collection.get(limit=min(10, total), include=["metadatas", "embeddings", "documents"])
            
            missing_metadata = 0
            missing_embeddings = 0
            missing_documents = 0
            
            for i in range(len(sample["ids"])):
                if not sample["metadatas"][i].get("scheme_name"):
                    missing_metadata += 1
                if sample.get("embeddings") is None or len(sample["embeddings"]) == 0:
                    missing_embeddings += 1
                if not sample["documents"][i]:
                    missing_documents += 1

            report["checks"]["metadata_present"] = missing_metadata == 0
            report["checks"]["embeddings_present"] = missing_embeddings == 0
            report["checks"]["documents_present"] = missing_documents == 0

            if missing_metadata > 0:
                report["errors"].append(f"{missing_metadata}/10 sample chunks missing scheme_name metadata")
            if missing_embeddings > 0:
                report["errors"].append(f"{missing_embeddings}/10 sample chunks missing embeddings")
            if missing_documents > 0:
                report["errors"].append(f"{missing_documents}/10 sample chunks missing documents")

            # Check 3: Similarity search works
            try:
                # Use first embedding as query
                test_embedding = sample["embeddings"][0]
                results = collection.query(
                    query_embeddings=[test_embedding],
                    n_results=3,
                    include=["distances"],
                )
                report["checks"]["similarity_search_works"] = len(results["ids"][0]) > 0
                if len(results["ids"][0]) == 0:
                    report["errors"].append("Similarity search returned no results")
            except Exception as e:
                report["checks"]["similarity_search_works"] = False
                report["errors"].append(f"Similarity search error: {str(e)}")

        # Check 4: Metadata filtering works
        if total > 0:
            try:
                filtered = collection.get(
                    where={"document_type": "webpage"},
                    limit=1,
                )
                report["checks"]["metadata_filtering_works"] = True
            except Exception as e:
                report["checks"]["metadata_filtering_works"] = False
                report["errors"].append(f"Metadata filtering error: {str(e)}")

        # Check 5: Persistence (verify client directory exists)
        persist_path = Path(self.persist_directory)
        report["checks"]["persistence_directory_exists"] = persist_path.exists()

        # Overall validity
        report["is_valid"] = (
            report["checks"].get("non_empty", False)
            and report["checks"].get("metadata_present", False)
            and report["checks"].get("embeddings_present", False)
            and report["checks"].get("documents_present", False)
            and report["checks"].get("similarity_search_works", False)
            and report["checks"].get("metadata_filtering_works", False)
            and report["checks"].get("persistence_directory_exists", False)
        )

        return report

    def delete_collection(self) -> bool:
        """
        Delete the entire collection (for reset/rebuild).

        Returns:
            True if deletion succeeded
        """
        try:
            client = self._get_client()
            client.delete_collection(name=self.collection_name)
            self._collection = None
            logger.info(f"Deleted collection: {self.collection_name}")
            return True
        except Exception as e:
            logger.error(f"Error deleting collection: {str(e)}")
            return False


if __name__ == "__main__":
    # Quick self-test
    indexer = Indexer(
        persist_directory="./test_chroma_db",
        collection_name="test_corpus",
    )
    test_chunks = [{
        "chunk_id": "test_0",
        "text": "HDFC Balanced Advantage Fund has an expense ratio of 0.81%.",
        "embedding": [0.1] * 384,  # Dummy embedding
        "section": "expense_ratio",
        "source_document_id": "test_doc",
        "metadata": {"document_id": "test_doc", "scheme_name": "HDFC BAF", "document_type": "webpage"},
        "structured_data": {"expense_ratio": "0.81%", "risk_level": "Very High Risk"},
        "scheme_name": "HDFC BAF",
        "embedding_model": "BAAI/bge-small-en-v1.5",
        "embedding_dimensions": 384,
    }]
    report = indexer.index_chunks(test_chunks)
    print(f"Indexed: {report['indexed_count']}, Total: {report['total_in_collection']}")
    
    # Clean up test
    indexer.delete_collection()
