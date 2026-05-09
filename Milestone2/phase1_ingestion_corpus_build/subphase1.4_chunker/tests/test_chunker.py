"""
Unit tests for chunker module
"""

import pytest
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from chunker import Chunker, Chunk


class TestChunker:
    """Test cases for Chunker class."""
    
    @pytest.fixture
    def chunker(self):
        """Create a Chunker instance for testing."""
        return Chunker(min_chunk_size=50, max_chunk_size=1000, chunk_overlap=100)
    
    def test_initialization(self, chunker):
        """Test chunker initialization."""
        assert chunker.min_chunk_size == 50
        assert chunker.max_chunk_size == 1000
        assert chunker.chunk_overlap == 100
    
    def test_chunk_by_sections(self, chunker):
        """Test section-based chunking."""
        sections = {
            'investment_objective': 'To provide returns that correspond to the Nifty 50 Index.',
            'exit_load': '1% if redeemed within 30 days.'
        }
        
        structured_data = {'expense_ratio': '0.5%'}
        document_metadata = {
            'document_id': 'test_doc',
            'scheme_name': 'Test Fund'
        }
        
        chunks = chunker._chunk_by_sections(
            sections,
            structured_data,
            document_metadata
        )
        
        assert len(chunks) == 2
        assert chunks[0].section == 'investment_objective'
        assert chunks[1].section == 'exit_load'
    
    def test_recursive_split(self, chunker):
        """Test recursive character splitting."""
        long_text = "This is a test. " * 100  # Long text
        
        chunks = chunker._recursive_split(long_text)
        
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk) <= chunker.max_chunk_size
    
    def test_chunk_by_recursion(self, chunker):
        """Test recursion-based chunking."""
        text = "This is a test. " * 100
        structured_data = {'expense_ratio': '0.5%'}
        document_metadata = {
            'document_id': 'test_doc',
            'scheme_name': 'Test Fund'
        }
        
        chunks = chunker._chunk_by_recursion(
            text,
            structured_data,
            document_metadata
        )
        
        assert len(chunks) > 0
        for chunk in chunks:
            assert len(chunk.text) >= chunker.min_chunk_size
    
    def test_validate_chunks(self, chunker):
        """Test chunk validation."""
        chunks = [
            Chunk(
                chunk_id='test1',
                text='Valid chunk with enough characters',
                metadata={},
                section='test',
                source_document_id='doc1',
                structured_data={}
            ),
            Chunk(
                chunk_id='test2',
                text='Too short',
                metadata={},
                section='test',
                source_document_id='doc1',
                structured_data={}
            )
        ]
        
        valid_chunks = chunker._validate_chunks(chunks)
        
        assert len(valid_chunks) == 1
        assert valid_chunks[0].chunk_id == 'test1'
    
    def test_chunk_document(self, chunker):
        """Test full document chunking."""
        sections = {
            'investment_objective': 'To provide returns that correspond to the Nifty 50 Index.',
            'exit_load': '1% if redeemed within 30 days.'
        }
        
        structured_data = {'expense_ratio': '0.5%'}
        document_metadata = {
            'document_id': 'test_doc',
            'scheme_name': 'Test Fund'
        }
        
        chunks = chunker.chunk_document(
            text="Full text",
            sections=sections,
            structured_data=structured_data,
            document_metadata=document_metadata
        )
        
        assert len(chunks) > 0
        for chunk in chunks:
            assert chunk.metadata.get('scheme_name') == 'Test Fund'
            assert len(chunk.structured_data) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
