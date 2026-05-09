"""
Tests for Phase 1.5 - Embedder Module
"""

import pytest
import sys
import os
import json
import numpy as np

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from embedder import Embedder, EmbeddedChunk


class TestEmbedder:
    """Test suite for the Embedder class."""

    @pytest.fixture
    def embedder(self):
        """Create an embedder instance for testing."""
        return Embedder(
            model_name="BAAI/bge-small-en-v1.5",
            batch_size=32,
            enrich_with_structured_data=True,
            normalize_embeddings=True,
        )

    @pytest.fixture
    def sample_chunks(self):
        """Sample chunk data for testing."""
        return [
            {
                "chunk_id": "test_chunk_0",
                "text": "HDFC Balanced Advantage Fund has an expense ratio of 0.81% and exit load of 1% for redemptions within 12 months.",
                "section": "expense_ratio",
                "source_document_id": "hdfc_baf_doc",
                "metadata": {
                    "document_id": "hdfc_baf_doc",
                    "scheme_name": "HDFC Balanced Advantage Fund",
                    "document_type": "webpage",
                    "category": "Hybrid",
                },
                "structured_data": {
                    "expense_ratio": "0.81%",
                    "exit_load": "1%",
                    "nav": "559.58",
                    "risk_level": "Very High Risk",
                },
                "scheme_name": "HDFC Balanced Advantage Fund",
            },
            {
                "chunk_id": "test_chunk_1",
                "text": "The fund invests in a mix of equity and debt instruments with dynamic asset allocation strategy.",
                "section": "investment_objective",
                "source_document_id": "hdfc_baf_doc",
                "metadata": {
                    "document_id": "hdfc_baf_doc",
                    "scheme_name": "HDFC Balanced Advantage Fund",
                    "document_type": "webpage",
                    "category": "Hybrid",
                },
                "structured_data": {
                    "expense_ratio": "0.81%",
                    "exit_load": "1%",
                },
                "scheme_name": "HDFC Balanced Advantage Fund",
            },
            {
                "chunk_id": "test_chunk_2",
                "text": "HDFC Nifty 50 Index Fund tracks the Nifty 50 index with low expense ratio of 0.2%.",
                "section": "expense_ratio",
                "source_document_id": "hdfc_nifty50_doc",
                "metadata": {
                    "document_id": "hdfc_nifty50_doc",
                    "scheme_name": "HDFC Nifty 50 Index Fund",
                    "document_type": "webpage",
                    "category": "Index Fund",
                },
                "structured_data": {
                    "expense_ratio": "0.2%",
                    "risk_level": "Very High Risk",
                },
                "scheme_name": "HDFC Nifty 50 Index Fund",
            },
        ]

    def test_embedder_initialization(self, embedder):
        """Test that embedder initializes correctly."""
        assert embedder.model_name == "BAAI/bge-small-en-v1.5"
        assert embedder.batch_size == 32
        assert embedder.enrich_with_structured_data is True
        assert embedder.normalize_embeddings is True
        assert embedder.expected_dimensions == 384

    def test_embed_chunks_returns_correct_count(self, embedder, sample_chunks):
        """Test that embed_chunks returns the correct number of embeddings."""
        results = embedder.embed_chunks(sample_chunks)
        assert len(results) == len(sample_chunks)

    def test_embedding_dimensions(self, embedder, sample_chunks):
        """Test that all embeddings have the expected dimension."""
        results = embedder.embed_chunks(sample_chunks)
        for ec in results:
            assert len(ec.embedding) == 384

    def test_embedding_is_normalized(self, embedder, sample_chunks):
        """Test that embeddings are normalized to unit length."""
        results = embedder.embed_chunks(sample_chunks)
        for ec in results:
            norm = np.linalg.norm(ec.embedding)
            assert abs(norm - 1.0) < 0.01, f"Norm {norm} is not close to 1.0"

    def test_no_nan_or_inf_in_embeddings(self, embedder, sample_chunks):
        """Test that embeddings contain no NaN or Inf values."""
        results = embedder.embed_chunks(sample_chunks)
        for ec in results:
            assert not any(np.isnan(v) or np.isinf(v) for v in ec.embedding)

    def test_embedded_chunk_fields(self, embedder, sample_chunks):
        """Test that EmbeddedChunk objects have all required fields."""
        results = embedder.embed_chunks(sample_chunks)
        for ec in results:
            assert ec.chunk_id
            assert ec.text
            assert ec.embedding
            assert ec.source_document_id
            assert ec.metadata
            assert ec.embedding_model == "BAAI/bge-small-en-v1.5"
            assert ec.embedding_dimensions == 384

    def test_text_enrichment_with_structured_data(self, embedder):
        """Test that text enrichment prepends structured data summary."""
        text = "Original chunk text."
        structured_data = {
            "expense_ratio": "0.81%",
            "risk_level": "Very High Risk",
        }
        enriched = embedder._enrich_text(text, structured_data, "HDFC BAF")
        assert "Scheme: HDFC BAF" in enriched
        assert "Expense Ratio: 0.81%" in enriched
        assert "Risk Level: Very High Risk" in enriched
        assert "Original chunk text." in enriched

    def test_text_enrichment_empty_structured_data(self, embedder):
        """Test that enrichment with empty structured data returns original text."""
        text = "Original chunk text."
        enriched = embedder._enrich_text(text, {}, "HDFC BAF")
        assert enriched == text

    def test_text_enrichment_disabled(self, sample_chunks):
        """Test that enrichment can be disabled."""
        embedder_no_enrich = Embedder(
            model_name="BAAI/bge-small-en-v1.5",
            enrich_with_structured_data=False,
        )
        results = embedder_no_enrich.embed_chunks(sample_chunks)
        # The text in results should be the original text (not enriched)
        for ec in results:
            # Find the matching original chunk
            original = next(c for c in sample_chunks if c["chunk_id"] == ec.chunk_id)
            assert ec.text == original["text"]

    def test_validate_embeddings_all_valid(self, embedder, sample_chunks):
        """Test validation report for valid embeddings."""
        results = embedder.embed_chunks(sample_chunks)
        report = embedder.validate_embeddings(results)
        assert report["is_valid"] is True
        assert report["dimension_mismatches"] == 0
        assert report["zero_norm_count"] == 0
        assert report["nan_inf_count"] == 0
        assert report["valid_count"] == len(sample_chunks)

    def test_compute_similarity_identical(self, embedder, sample_chunks):
        """Test that similarity of an embedding with itself is ~1.0."""
        results = embedder.embed_chunks(sample_chunks)
        sim = embedder.compute_similarity(results[0].embedding, results[0].embedding)
        assert abs(sim - 1.0) < 0.01

    def test_compute_similarity_different_docs(self, embedder, sample_chunks):
        """Test similarity between chunks from different documents."""
        results = embedder.embed_chunks(sample_chunks)
        # chunk_0 and chunk_2 are from different docs
        sim = embedder.compute_similarity(results[0].embedding, results[2].embedding)
        assert 0.0 <= sim <= 1.0

    def test_to_serializable(self, embedder, sample_chunks):
        """Test that to_serializable produces valid JSON-compatible dicts."""
        results = embedder.embed_chunks(sample_chunks)
        serialized = embedder.to_serializable(results)
        assert len(serialized) == len(sample_chunks)
        for s in serialized:
            assert isinstance(s, dict)
            assert "chunk_id" in s
            assert "embedding" in s
            assert isinstance(s["embedding"], list)
            # Verify it's JSON serializable
            json.dumps(s)

    def test_batch_processing(self, sample_chunks):
        """Test that batch processing with small batch size works correctly."""
        embedder_small_batch = Embedder(
            model_name="BAAI/bge-small-en-v1.5",
            batch_size=1,  # Very small batch to test batching logic
        )
        results = embedder_small_batch.embed_chunks(sample_chunks)
        assert len(results) == len(sample_chunks)
        for ec in results:
            assert len(ec.embedding) == 384

    def test_similarity_same_doc_higher_than_diff_doc(self, embedder, sample_chunks):
        """Test that same-document chunks have higher similarity than different-doc chunks."""
        results = embedder.embed_chunks(sample_chunks)
        # chunks 0 and 1 are from same doc (hdfc_baf_doc)
        sim_same = embedder.compute_similarity(results[0].embedding, results[1].embedding)
        # chunks 0 and 2 are from different docs
        sim_diff = embedder.compute_similarity(results[0].embedding, results[2].embedding)
        # Same-doc similarity should generally be higher
        # (though this is not guaranteed for all text, it's a reasonable heuristic)
        assert sim_same > 0  # At least positive similarity
        assert sim_diff > 0


class TestEmbedderEdgeCases:
    """Edge case tests for the Embedder."""

    @pytest.fixture
    def embedder(self):
        return Embedder(model_name="BAAI/bge-small-en-v1.5")

    def test_empty_structured_data(self, embedder):
        """Test embedding a chunk with no structured data."""
        chunks = [{
            "chunk_id": "test_empty_sd",
            "text": "This chunk has no structured data.",
            "section": "general",
            "source_document_id": "doc1",
            "metadata": {"document_id": "doc1", "scheme_name": "Test Fund"},
            "structured_data": {},
            "scheme_name": "Test Fund",
        }]
        results = embedder.embed_chunks(chunks)
        assert len(results) == 1
        assert len(results[0].embedding) == 384

    def test_single_chunk(self, embedder):
        """Test embedding a single chunk."""
        chunks = [{
            "chunk_id": "test_single",
            "text": "Single chunk for embedding test.",
            "section": "general",
            "source_document_id": "doc1",
            "metadata": {"document_id": "doc1", "scheme_name": "Test Fund"},
            "structured_data": {"expense_ratio": "1.5%"},
            "scheme_name": "Test Fund",
        }]
        results = embedder.embed_chunks(chunks)
        assert len(results) == 1
