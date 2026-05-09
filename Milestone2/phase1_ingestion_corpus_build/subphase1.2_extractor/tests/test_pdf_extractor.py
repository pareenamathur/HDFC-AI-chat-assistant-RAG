"""
Unit tests for pdf_extractor module
"""

import pytest
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from pdf_extractor import PDFExtractor, ExtractedContent


class TestPDFExtractor:
    """Test cases for PDFExtractor class."""
    
    @pytest.fixture
    def extractor(self):
        """Create a PDFExtractor instance for testing."""
        return PDFExtractor(use_ocr_fallback=False)
    
    def test_initialization(self, extractor):
        """Test extractor initialization."""
        assert extractor.use_ocr_fallback == False
        assert extractor.ocr_available is not None
    
    def test_extract_nonexistent_file(self, extractor):
        """Test extraction of non-existent file."""
        result = extractor.extract_pdf("nonexistent.pdf")
        
        assert isinstance(result, ExtractedContent)
        assert result.filepath == "nonexistent.pdf"
        assert result.error == "File not found"
    
    def test_extract_structured_data(self, extractor):
        """Test structured data extraction."""
        text = """
        HDFC Nifty50 Fund
        Expense Ratio: 0.5%
        Exit Load: 1%
        SIP Amount: Rs 500
        """
        
        structured_data = extractor._extract_structured_data(text)
        
        assert 'expense_ratio' in structured_data
        assert 'exit_load' in structured_data
        assert 'sip_amount' in structured_data
    
    def test_extract_sections(self, extractor):
        """Test section extraction."""
        text = """
        INVESTMENT OBJECTIVE:
        To provide returns that correspond to the total returns of the Nifty 50 Index.
        
        EXIT LOAD:
        1% if redeemed within 30 days.
        """
        
        sections = extractor._extract_sections(text)
        
        assert 'investment_objective' in sections
        assert 'exit_load' in sections


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
