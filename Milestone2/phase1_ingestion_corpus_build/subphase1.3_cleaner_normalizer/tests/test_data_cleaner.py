"""
Unit tests for data_cleaner module
"""

import pytest
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from data_cleaner import DataCleaner, CleanedContent


class TestDataCleaner:
    """Test cases for DataCleaner class."""
    
    @pytest.fixture
    def cleaner(self):
        """Create a DataCleaner instance for testing."""
        return DataCleaner()
    
    def test_initialization(self, cleaner):
        """Test cleaner initialization."""
        assert cleaner.term_mapping is not None
        assert 'expense ratio' in cleaner.term_mapping
        assert cleaner.boilerplate_patterns is not None
    
    def test_clean_text(self, cleaner):
        """Test text cleaning."""
        text = """
        HDFC Nifty50 Fund
        Expense Ratio: 0.5%
        TER: 0.5%
        *All investments are subject to market risks*
        """
        
        result = cleaner.clean_text(text)
        
        assert isinstance(result, CleanedContent)
        assert result.cleaned_text is not None
        assert len(result.cleaned_text) < len(result.original_text)
    
    def test_term_normalization(self, cleaner):
        """Test term normalization."""
        text = "The expense ratio is 0.5% and TER is also 0.5%"
        
        result = cleaner.clean_text(text)
        
        assert 'expense_ratio' in result.normalized_terms
        assert result.cleaned_text.count('expense_ratio') >= 1
    
    def test_remove_headers_footers(self, cleaner):
        """Test header/footer removal."""
        text = """
        Page 1 of 5
        HDFC Nifty50 Fund
        Expense Ratio: 0.5%
        www.hdfcfund.com
        """
        
        cleaned = cleaner.remove_headers_footers(text)
        
        assert "Page 1 of 5" not in cleaned
        assert "HDFC Nifty50 Fund" in cleaned
    
    def test_normalize_dates(self, cleaner):
        """Test date normalization."""
        text = "01/01/2024"
        
        normalized = cleaner.normalize_dates(text)
        
        assert "2024-01-01" in normalized


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
