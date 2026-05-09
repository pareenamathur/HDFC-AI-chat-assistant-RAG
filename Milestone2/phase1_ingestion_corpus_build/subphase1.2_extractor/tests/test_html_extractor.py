"""
Unit tests for html_extractor module
"""

import pytest
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from html_extractor import HTMLExtractor, HTMLExtractedContent


class TestHTMLExtractor:
    """Test cases for HTMLExtractor class."""
    
    @pytest.fixture
    def extractor(self):
        """Create an HTMLExtractor instance for testing."""
        return HTMLExtractor()
    
    def test_initialization(self, extractor):
        """Test extractor initialization."""
        assert extractor is not None
    
    def test_extract_html(self, extractor):
        """Test HTML extraction."""
        html = """
        <html>
            <head><title>HDFC Nifty50 Fund - Groww</title></head>
            <body>
                <h1>HDFC Nifty50 Fund</h1>
                <p>Expense Ratio: 0.5%</p>
            </body>
        </html>
        """
        
        result = extractor.extract_html(html, "https://example.com")
        
        assert isinstance(result, HTMLExtractedContent)
        assert result.scheme_name == "HDFC Nifty50 Fund"
        assert result.structured_data.get('expense_ratio') == '0.5%'
    
    def test_extract_scheme_name(self, extractor):
        """Test scheme name extraction."""
        html = '<html><head><title>HDFC Nifty50 Fund - Groww</title></head></html>'
        
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        
        scheme_name = extractor._extract_scheme_name(soup, "https://example.com")
        
        assert scheme_name == "HDFC Nifty50 Fund"
    
    def test_extract_document_links(self, extractor):
        """Test document link extraction."""
        html = """
        <html>
            <body>
                <a href="/factsheet.pdf">Download Factsheet</a>
                <a href="/kim.pdf">KIM Document</a>
            </body>
        </html>
        """
        
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        
        links = extractor._extract_document_links(soup, "https://example.com")
        
        assert len(links) >= 2
        assert any(link['type'] == 'factsheet' for link in links)
        assert any(link['type'] == 'kim' for link in links)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
