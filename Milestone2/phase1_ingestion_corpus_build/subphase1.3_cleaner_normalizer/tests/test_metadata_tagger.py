"""
Unit tests for metadata_tagger module
"""

import pytest
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from metadata_tagger import MetadataTagger, TaggedDocument


class TestMetadataTagger:
    """Test cases for MetadataTagger class."""
    
    @pytest.fixture
    def tagger(self):
        """Create a MetadataTagger instance for testing."""
        return MetadataTagger()
    
    def test_initialization(self, tagger):
        """Test tagger initialization."""
        assert tagger.document_types is not None
        assert 'factsheet' in tagger.document_types
    
    def test_tag_document(self, tagger):
        """Test document tagging."""
        tagged = tagger.tag_document(
            scheme_name="HDFC Nifty50 Fund",
            document_type="factsheet",
            source_url="https://example.com/factsheet.pdf",
            content="This is the content",
            category="Index Fund"
        )
        
        assert isinstance(tagged, TaggedDocument)
        assert tagged.scheme_name == "HDFC Nifty50 Fund"
        assert tagged.document_type == "factsheet"
        assert tagged.document_id is not None
        assert tagged.content_hash is not None
    
    def test_generate_document_id(self, tagger):
        """Test document ID generation."""
        doc_id = tagger._generate_document_id(
            "HDFC Nifty50 Fund",
            "factsheet",
            "https://example.com/factsheet.pdf"
        )
        
        assert doc_id is not None
        assert len(doc_id) > 0
        assert "hdfc" in doc_id.lower()
    
    def test_generate_content_hash(self, tagger):
        """Test content hash generation."""
        content = "This is test content"
        content_hash = tagger._generate_content_hash(content)
        
        assert content_hash is not None
        assert len(content_hash) == 64  # SHA-256 produces 64 hex characters
    
    def test_normalize_document_type(self, tagger):
        """Test document type normalization."""
        normalized = tagger._normalize_document_type("Factsheet PDF")
        
        assert normalized == "factsheet"
    
    def test_deduplicate_documents(self, tagger):
        """Test document deduplication."""
        docs = [
            tagger.tag_document("HDFC Fund", "factsheet", "url1", "content1", "Index"),
            tagger.tag_document("HDFC Fund", "factsheet", "url2", "content1", "Index"),  # Duplicate content
            tagger.tag_document("HDFC Fund", "kim", "url3", "content2", "Index"),
        ]
        
        unique_docs = tagger.deduplicate_documents(docs)
        
        assert len(unique_docs) == 2  # One duplicate removed


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
