"""
Embedder Module - Phase 1.5
Generates vector embeddings for text chunks using BAAI/bge-small-en-v1.5.
Uses ChromaDB's SentenceTransformerEmbeddingFunction (ONNX runtime, no torch needed).
"""

from typing import Dict, List, Optional, Any
import logging
from dataclasses import dataclass, field
import hashlib
import json
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class EmbeddedChunk:
    """Data class to hold a chunk with its embedding vector."""
    chunk_id: str
    text: str
    embedding: List[float]
    section: str
    source_document_id: str
    metadata: Dict[str, Any]
    structured_data: Dict[str, Any]
    embedding_model: str = ""
    embedding_dimensions: int = 0
    scheme_name: str = ""


class Embedder:
    """Generates vector embeddings for text chunks."""

    # Supported models and their dimensions
    MODEL_DIMENSIONS = {
        "BAAI/bge-small-en-v1.5": 384,
        "all-MiniLM-L6-v2": 384,
        "text-embedding-3-small": 1536,  # OpenAI - placeholder for future support
    }

    def __init__(
        self,
        model_name: str = "BAAI/bge-small-en-v1.5",
        batch_size: int = 64,
        enrich_with_structured_data: bool = True,
        normalize_embeddings: bool = True,
    ):
        """
        Initialize the embedder.

        Args:
            model_name: Name of the embedding model to use
            batch_size: Number of texts to embed per batch
            enrich_with_structured_data: Whether to prepend structured data summary to chunk text
            normalize_embeddings: Whether to normalize embedding vectors
        """
        self.model_name = model_name
        self.batch_size = batch_size
        self.enrich_with_structured_data = enrich_with_structured_data
        self.normalize_embeddings = normalize_embeddings
        self.expected_dimensions = self.MODEL_DIMENSIONS.get(model_name, 384)
        self._embedding_function = None

    def _get_embedding_function(self):
        """Lazy-load the embedding function to avoid loading model at import time."""
        if self._embedding_function is None:
            from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
            logger.info(f"Loading embedding model: {self.model_name}")
            self._embedding_function = SentenceTransformerEmbeddingFunction(
                model_name=self.model_name,
                device="cpu",
            )
            logger.info(f"Model loaded successfully. Expected dimensions: {self.expected_dimensions}")
        return self._embedding_function

    def _enrich_text(self, text: str, structured_data: Dict[str, Any], scheme_name: str) -> str:
        """
        Enrich chunk text with structured data summary for better embedding quality.
        Per architecture.md: Attach extracted structured data as context to relevant chunks.

        Args:
            text: Original chunk text
            structured_data: Extracted structured fields
            scheme_name: Name of the scheme

        Returns:
            Enriched text with structured data prepended
        """
        if not structured_data:
            return text

        summary_parts = [f"Scheme: {scheme_name}"]

        field_labels = {
            "expense_ratio": "Expense Ratio",
            "exit_load": "Exit Load",
            "nav": "NAV",
            "aum": "AUM",
            "sip_minimum": "Minimum SIP",
            "risk_level": "Risk Level",
            "category": "Category",
            "benchmark": "Benchmark",
        }

        for key, label in field_labels.items():
            if key in structured_data and structured_data[key]:
                summary_parts.append(f"{label}: {structured_data[key]}")

        summary = ". ".join(summary_parts) + ". "
        return summary + text

    def embed_chunks(self, chunks: List[Dict[str, Any]]) -> List[EmbeddedChunk]:
        """
        Generate embeddings for a list of chunk dictionaries.

        Args:
            chunks: List of chunk dicts from Phase 1.4 output

        Returns:
            List of EmbeddedChunk objects with embedding vectors
        """
        ef = self._get_embedding_function()

        embedded_chunks = []
        all_texts = []

        # Prepare texts for embedding (with optional enrichment)
        for chunk in chunks:
            text = chunk.get("text", "")
            structured_data = chunk.get("structured_data", {})
            scheme_name = chunk.get("scheme_name", chunk.get("metadata", {}).get("scheme_name", ""))

            if self.enrich_with_structured_data and structured_data:
                text = self._enrich_text(text, structured_data, scheme_name)

            all_texts.append(text)

        # Batch processing
        total_chunks = len(all_texts)
        logger.info(f"Embedding {total_chunks} chunks in batches of {self.batch_size}")

        all_embeddings = []
        for i in range(0, total_chunks, self.batch_size):
            batch_texts = all_texts[i:i + self.batch_size]
            batch_num = i // self.batch_size + 1
            total_batches = (total_chunks + self.batch_size - 1) // self.batch_size
            logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch_texts)} chunks)")

            batch_embeddings = ef(batch_texts)
            all_embeddings.extend(batch_embeddings)

        # Build EmbeddedChunk objects
        for idx, chunk in enumerate(chunks):
            embedding = all_embeddings[idx]

            # Normalize if requested
            if self.normalize_embeddings:
                embedding = self._normalize_vector(embedding)

            embedded_chunk = EmbeddedChunk(
                chunk_id=chunk.get("chunk_id", f"chunk_{idx}"),
                text=chunk.get("text", ""),
                embedding=embedding,
                section=chunk.get("section", "general"),
                source_document_id=chunk.get("source_document_id", ""),
                metadata=chunk.get("metadata", {}),
                structured_data=chunk.get("structured_data", {}),
                embedding_model=self.model_name,
                embedding_dimensions=len(embedding),
                scheme_name=chunk.get("scheme_name", chunk.get("metadata", {}).get("scheme_name", "")),
            )
            embedded_chunks.append(embedded_chunk)

        logger.info(f"Embedded {len(embedded_chunks)} chunks successfully")
        return embedded_chunks

    def _normalize_vector(self, embedding: List[float]) -> List[float]:
        """Normalize an embedding vector to unit length."""
        vec = np.array(embedding, dtype=np.float32)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()

    def validate_embeddings(self, embedded_chunks: List[EmbeddedChunk]) -> Dict[str, Any]:
        """
        Validate generated embeddings per architecture.md requirements.

        Checks:
        1. Embedding dimensions match expected dimensions
        2. All embeddings have non-zero norm
        3. No NaN or Inf values
        4. Metadata is properly attached

        Args:
            embedded_chunks: List of EmbeddedChunk objects to validate

        Returns:
            Validation report dictionary
        """
        report = {
            "total_chunks": len(embedded_chunks),
            "model": self.model_name,
            "expected_dimensions": self.expected_dimensions,
            "dimension_mismatches": 0,
            "zero_norm_count": 0,
            "nan_inf_count": 0,
            "missing_metadata_count": 0,
            "valid_count": 0,
            "dimension_distribution": {},
            "errors": [],
        }

        for ec in embedded_chunks:
            is_valid = True

            # Check dimensions
            actual_dims = len(ec.embedding)
            report["dimension_distribution"][actual_dims] = report["dimension_distribution"].get(actual_dims, 0) + 1
            if actual_dims != self.expected_dimensions:
                report["dimension_mismatches"] += 1
                report["errors"].append(
                    f"Chunk {ec.chunk_id}: dimension mismatch (expected {self.expected_dimensions}, got {actual_dims})"
                )
                is_valid = False

            # Check for zero norm
            norm = np.linalg.norm(ec.embedding)
            if norm == 0:
                report["zero_norm_count"] += 1
                report["errors"].append(f"Chunk {ec.chunk_id}: zero-norm embedding")
                is_valid = False

            # Check for NaN/Inf
            if any(np.isnan(v) or np.isinf(v) for v in ec.embedding):
                report["nan_inf_count"] += 1
                report["errors"].append(f"Chunk {ec.chunk_id}: NaN or Inf in embedding")
                is_valid = False

            # Check metadata
            if not ec.metadata or not ec.source_document_id:
                report["missing_metadata_count"] += 1
                report["errors"].append(f"Chunk {ec.chunk_id}: missing metadata")
                is_valid = False

            if is_valid:
                report["valid_count"] += 1

        report["is_valid"] = (
            report["dimension_mismatches"] == 0
            and report["zero_norm_count"] == 0
            and report["nan_inf_count"] == 0
        )

        return report

    def to_serializable(self, embedded_chunks: List[EmbeddedChunk]) -> List[Dict[str, Any]]:
        """
        Convert embedded chunks to a JSON-serializable format for storage.

        Args:
            embedded_chunks: List of EmbeddedChunk objects

        Returns:
            List of dictionaries ready for JSON serialization
        """
        result = []
        for ec in embedded_chunks:
            result.append({
                "chunk_id": ec.chunk_id,
                "text": ec.text,
                "embedding": ec.embedding,
                "section": ec.section,
                "source_document_id": ec.source_document_id,
                "metadata": ec.metadata,
                "structured_data": ec.structured_data,
                "embedding_model": ec.embedding_model,
                "embedding_dimensions": ec.embedding_dimensions,
                "scheme_name": ec.scheme_name,
            })
        return result

    def compute_similarity(
        self,
        embedding1: List[float],
        embedding2: List[float],
    ) -> float:
        """
        Compute cosine similarity between two embeddings.

        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector

        Returns:
            Cosine similarity score
        """
        v1 = np.array(embedding1, dtype=np.float32)
        v2 = np.array(embedding2, dtype=np.float32)
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(np.dot(v1, v2) / (norm1 * norm2))


if __name__ == "__main__":
    # Quick self-test
    embedder = Embedder(model_name="BAAI/bge-small-en-v1.5")
    test_chunks = [
        {
            "chunk_id": "test_0",
            "text": "HDFC Balanced Advantage Fund has an expense ratio of 0.81%.",
            "section": "expense_ratio",
            "source_document_id": "test_doc",
            "metadata": {"document_id": "test_doc", "scheme_name": "HDFC Balanced Advantage Fund"},
            "structured_data": {"expense_ratio": "0.81%", "risk_level": "Very High Risk"},
            "scheme_name": "HDFC Balanced Advantage Fund",
        }
    ]
    results = embedder.embed_chunks(test_chunks)
    report = embedder.validate_embeddings(results)
    print(f"Validation: {report['is_valid']}, Dims: {results[0].embedding_dimensions}")
