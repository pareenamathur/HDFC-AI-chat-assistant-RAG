"""
Tests for Phase 1.6 - Indexer Module
"""

import pytest
import sys
import os
import json
import tempfile
import shutil

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from indexer import Indexer


@pytest.fixture
def temp_chroma_dir():
    """Create a temporary directory for ChromaDB persistence."""
    tmpdir = tempfile.mkdtemp(prefix="test_chroma_")
    yield tmpdir
    # Cleanup
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def indexer(temp_chroma_dir):
    """Create an indexer instance with temp persistence."""
    return Indexer(
        persist_directory=temp_chroma_dir,
        collection_name="test_corpus",
        embedding_model_name="BAAI/bge-small-en-v1.5",
    )


@pytest.fixture
def sample_chunks():
    """Sample embedded chunks for testing."""
    dummy_embedding = [0.1] * 384
    return [
        {
            "chunk_id": "test_chunk_0",
            "text": "HDFC Balanced Advantage Fund has an expense ratio of 0.81%.",
            "embedding": dummy_embedding,
            "section": "expense_ratio",
            "source_document_id": "hdfc_baf_doc",
            "metadata": {
                "document_id": "hdfc_baf_doc",
                "scheme_name": "HDFC Balanced Advantage Fund",
                "document_type": "webpage",
                "source_url": "https://example.com/baf",
                "category": "Hybrid",
                "content_length": 1000,
                "chunk_number": 0,
                "chunk_length": 67,
            },
            "structured_data": {
                "expense_ratio": "0.81%",
                "exit_load": "1%",
                "nav": "559.58",
                "risk_level": "Very High Risk",
            },
            "scheme_name": "HDFC Balanced Advantage Fund",
            "embedding_model": "BAAI/bge-small-en-v1.5",
            "embedding_dimensions": 384,
        },
        {
            "chunk_id": "test_chunk_1",
            "text": "The fund invests in a mix of equity and debt instruments with dynamic asset allocation.",
            "embedding": [0.2] * 384,
            "section": "investment_objective",
            "source_document_id": "hdfc_baf_doc",
            "metadata": {
                "document_id": "hdfc_baf_doc",
                "scheme_name": "HDFC Balanced Advantage Fund",
                "document_type": "webpage",
                "source_url": "https://example.com/baf",
                "category": "Hybrid",
                "content_length": 1000,
                "chunk_number": 1,
                "chunk_length": 79,
            },
            "structured_data": {
                "expense_ratio": "0.81%",
                "exit_load": "1%",
            },
            "scheme_name": "HDFC Balanced Advantage Fund",
            "embedding_model": "BAAI/bge-small-en-v1.5",
            "embedding_dimensions": 384,
        },
        {
            "chunk_id": "test_chunk_2",
            "text": "HDFC Nifty 50 Index Fund tracks the Nifty 50 index with low expense ratio of 0.2%.",
            "embedding": [0.3] * 384,
            "section": "expense_ratio",
            "source_document_id": "hdfc_nifty50_doc",
            "metadata": {
                "document_id": "hdfc_nifty50_doc",
                "scheme_name": "HDFC Nifty 50 Index Fund",
                "document_type": "webpage",
                "source_url": "https://example.com/nifty50",
                "category": "Index Fund",
                "content_length": 800,
                "chunk_number": 0,
                "chunk_length": 79,
            },
            "structured_data": {
                "expense_ratio": "0.2%",
                "risk_level": "Very High Risk",
            },
            "scheme_name": "HDFC Nifty 50 Index Fund",
            "embedding_model": "BAAI/bge-small-en-v1.5",
            "embedding_dimensions": 384,
        },
    ]


class TestIndexer:
    """Test suite for the Indexer class."""

    def test_indexer_initialization(self, indexer, temp_chroma_dir):
        """Test that indexer initializes correctly."""
        assert indexer.persist_directory == temp_chroma_dir
        assert indexer.collection_name == "test_corpus"
        assert indexer.embedding_model_name == "BAAI/bge-small-en-v1.5"

    def test_index_chunks_basic(self, indexer, sample_chunks):
        """Test basic chunk indexing into ChromaDB."""
        report = indexer.index_chunks(sample_chunks)
        assert report["indexed_count"] == 3
        assert report["error_count"] == 0
        assert report["total_in_collection"] == 3

    def test_index_chunks_duplicate_skip(self, indexer, sample_chunks):
        """Test that duplicate chunks are skipped on re-index."""
        # First indexing
        report1 = indexer.index_chunks(sample_chunks)
        assert report1["indexed_count"] == 3

        # Second indexing - all should be skipped
        report2 = indexer.index_chunks(sample_chunks)
        assert report2["skipped_count"] == 3
        assert report2["indexed_count"] == 0
        assert report2["total_in_collection"] == 3

    def test_metadata_preparation(self, indexer, sample_chunks):
        """Test that metadata is properly prepared for ChromaDB."""
        metadata = indexer._prepare_metadata(sample_chunks[0])
        assert metadata["section"] == "expense_ratio"
        assert metadata["scheme_name"] == "HDFC Balanced Advantage Fund"
        assert metadata["document_type"] == "webpage"
        assert metadata["category"] == "Hybrid"
        assert metadata["sd_expense_ratio"] == "0.81%"
        assert metadata["sd_risk_level"] == "Very High Risk"
        assert isinstance(metadata["chunk_number"], int)
        assert isinstance(metadata["embedding_dimensions"], int)

    def test_metadata_flattening(self, indexer, sample_chunks):
        """Test that nested structured_data is flattened with sd_ prefix."""
        metadata = indexer._prepare_metadata(sample_chunks[0])
        # Structured data fields should be prefixed with sd_
        assert "sd_expense_ratio" in metadata
        assert "sd_exit_load" in metadata
        assert "sd_nav" in metadata
        assert "sd_risk_level" in metadata

    def test_get_collection_stats(self, indexer, sample_chunks):
        """Test collection statistics retrieval."""
        indexer.index_chunks(sample_chunks)
        stats = indexer.get_collection_stats()
        assert stats["total_chunks"] == 3
        assert stats["unique_schemes"] == 2
        assert "HDFC Balanced Advantage Fund" in stats["scheme_counts"]
        assert "HDFC Nifty 50 Index Fund" in stats["scheme_counts"]

    def test_validate_index_valid(self, indexer, sample_chunks):
        """Test validation of a properly indexed collection."""
        indexer.index_chunks(sample_chunks)
        report = indexer.validate_index()
        assert report["is_valid"] is True
        assert report["checks"]["non_empty"] is True
        assert report["checks"]["metadata_present"] is True
        assert report["checks"]["embeddings_present"] is True
        assert report["checks"]["documents_present"] is True
        assert report["checks"]["similarity_search_works"] is True
        assert report["checks"]["metadata_filtering_works"] is True

    def test_validate_index_empty(self, indexer):
        """Test validation of an empty collection."""
        # Get collection but don't add anything
        indexer._get_or_create_collection()
        report = indexer.validate_index()
        assert report["is_valid"] is False
        assert report["checks"]["non_empty"] is False

    def test_query_by_embedding(self, indexer, sample_chunks):
        """Test querying by embedding vector."""
        indexer.index_chunks(sample_chunks)
        query_embedding = [0.15] * 384  # Between 0.1 and 0.2
        results = indexer.query(query_embedding, n_results=2)
        assert len(results["ids"][0]) == 2
        assert "distances" in results
        assert "metadatas" in results

    def test_query_with_metadata_filter(self, indexer, sample_chunks):
        """Test querying with metadata filtering."""
        indexer.index_chunks(sample_chunks)
        query_embedding = [0.15] * 384
        results = indexer.query(
            query_embedding,
            n_results=5,
            where={"scheme_name": "HDFC Nifty 50 Index Fund"},
        )
        # Should only return chunks from HDFC Nifty 50
        for meta in results["metadatas"][0]:
            assert meta["scheme_name"] == "HDFC Nifty 50 Index Fund"

    def test_persistence(self, temp_chroma_dir, sample_chunks):
        """Test that data persists across indexer instances."""
        # Index with first instance
        indexer1 = Indexer(
            persist_directory=temp_chroma_dir,
            collection_name="test_corpus",
        )
        indexer1.index_chunks(sample_chunks)
        stats1 = indexer1.get_collection_stats()
        assert stats1["total_chunks"] == 3

        # Create new instance pointing to same directory
        indexer2 = Indexer(
            persist_directory=temp_chroma_dir,
            collection_name="test_corpus",
        )
        stats2 = indexer2.get_collection_stats()
        assert stats2["total_chunks"] == 3

    def test_delete_collection(self, indexer, sample_chunks):
        """Test collection deletion."""
        indexer.index_chunks(sample_chunks)
        assert indexer._get_or_create_collection().count() == 3

        result = indexer.delete_collection()
        assert result is True

        # After deletion, get_collection_stats should create fresh collection
        stats = indexer.get_collection_stats()
        assert stats["total_chunks"] == 0

    def test_index_chunks_missing_embedding(self, indexer):
        """Test handling of chunks with missing embeddings."""
        chunks = [
            {
                "chunk_id": "test_no_embed",
                "text": "This chunk has no embedding.",
                "embedding": None,
                "section": "general",
                "source_document_id": "doc1",
                "metadata": {},
                "structured_data": {},
                "scheme_name": "Test Fund",
            }
        ]
        report = indexer.index_chunks(chunks)
        assert report["error_count"] == 1
        assert report["indexed_count"] == 0

    def test_index_chunks_missing_text(self, indexer):
        """Test handling of chunks with missing text."""
        chunks = [
            {
                "chunk_id": "test_no_text",
                "text": "",
                "embedding": [0.1] * 384,
                "section": "general",
                "source_document_id": "doc1",
                "metadata": {},
                "structured_data": {},
                "scheme_name": "Test Fund",
            }
        ]
        report = indexer.index_chunks(chunks)
        assert report["error_count"] == 1
        assert report["indexed_count"] == 0


class TestIndexerEdgeCases:
    """Edge case tests for the Indexer."""

    @pytest.fixture
    def indexer(self):
        """Create an indexer with temp directory."""
        tmpdir = tempfile.mkdtemp(prefix="test_chroma_edge_")
        idx = Indexer(
            persist_directory=tmpdir,
            collection_name="test_edge_corpus",
        )
        yield idx
        shutil.rmtree(tmpdir, ignore_errors=True)

    def test_empty_chunks_list(self, indexer):
        """Test indexing an empty list of chunks."""
        report = indexer.index_chunks([])
        assert report["indexed_count"] == 0
        assert report["total_in_collection"] == 0

    def test_large_batch_indexing(self, indexer):
        """Test indexing with small batch size to verify batching logic."""
        # Create 5 chunks, index with batch_size=2
        chunks = []
        for i in range(5):
            chunks.append({
                "chunk_id": f"batch_test_{i}",
                "text": f"Test chunk number {i} for batch indexing.",
                "embedding": [0.1 + i * 0.01] * 384,
                "section": "general",
                "source_document_id": "batch_doc",
                "metadata": {"scheme_name": f"Test Fund {i}", "document_type": "webpage"},
                "structured_data": {},
                "scheme_name": f"Test Fund {i}",
                "embedding_model": "BAAI/bge-small-en-v1.5",
                "embedding_dimensions": 384,
            })

        report = indexer.index_chunks(chunks, batch_size=2)
        assert report["indexed_count"] == 5
        assert report["batch_count"] == 3  # ceil(5/2) = 3

    def test_metadata_all_string_types(self, indexer):
        """Test that all metadata values are ChromaDB-compatible types."""
        chunk = {
            "chunk_id": "type_test",
            "text": "Type test chunk.",
            "embedding": [0.1] * 384,
            "section": "general",
            "source_document_id": "doc1",
            "metadata": {
                "scheme_name": "Test Fund",
                "document_type": "webpage",
                "content_length": 500,
                "chunk_number": 0,
            },
            "structured_data": {
                "expense_ratio": "0.5%",
                "nav": "100.50",
            },
            "scheme_name": "Test Fund",
            "embedding_model": "BAAI/bge-small-en-v1.5",
            "embedding_dimensions": 384,
        }

        metadata = indexer._prepare_metadata(chunk)
        # ChromaDB accepts str, int, float, bool
        for key, value in metadata.items():
            assert isinstance(value, (str, int, float, bool)), \
                f"Metadata key '{key}' has invalid type: {type(value)}"
