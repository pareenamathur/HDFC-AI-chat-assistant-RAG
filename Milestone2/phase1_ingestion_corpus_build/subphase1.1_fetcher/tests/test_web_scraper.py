"""
Unit tests for web_scraper module
"""

import pytest
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from web_scraper import WebScraper, ScrapedContent


class TestWebScraper:
    """Test cases for WebScraper class."""
    
    @pytest.fixture
    def scraper(self):
        """Create a WebScraper instance for testing."""
        return WebScraper(request_delay=0.5, timeout=30)
    
    def test_initialization(self, scraper):
        """Test scraper initialization."""
        assert scraper.request_delay == 0.5
        assert scraper.timeout == 30
        assert scraper.headers is not None
        assert 'User-Agent' in scraper.headers
        assert scraper.session is not None
    
    def test_scrape_valid_url(self, scraper):
        """Test scraping a valid URL."""
        result = scraper.scrape_url("https://httpbin.org/html")
        
        assert isinstance(result, ScrapedContent)
        assert result.url == "https://httpbin.org/html"
        assert result.is_valid == True
        assert result.html is not None
        assert len(result.html) > 0
        assert result.status_code == 200
    
    def test_scrape_invalid_url(self, scraper):
        """Test scraping an invalid URL."""
        result = scraper.scrape_url("https://httpbin.org/status/404")
        
        assert isinstance(result, ScrapedContent)
        assert result.url == "https://httpbin.org/status/404"
        assert result.is_valid == False
        assert result.status_code == 404
    
    def test_extract_scheme_name_from_title(self, scraper):
        """Test scheme name extraction from title."""
        title = "HDFC Nifty50 Equal Weight Index Fund - Groww"
        scheme_name = scraper._extract_scheme_name(title, "https://example.com")
        
        assert scheme_name == "HDFC Nifty50 Equal Weight Index Fund"
    
    def test_extract_scheme_name_from_url(self, scraper):
        """Test scheme name extraction from URL."""
        url = "https://groww.in/mutual-funds/hdfc-nifty50-equal-weight-index-fund-direct-growth"
        scheme_name = scraper._extract_scheme_name("", url)
        
        assert "Hdfc" in scheme_name
        assert "Nifty50" in scheme_name
    
    def test_extract_links(self, scraper):
        """Test link extraction."""
        html = """
        <html>
            <body>
                <a href="/link1">Link 1</a>
                <a href="https://example.com/link2">Link 2</a>
            </body>
        </html>
        """
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        
        links = scraper._extract_links(soup, "https://example.com")
        
        assert len(links) == 2
        assert any("link1" in link for link in links)
        assert any("link2" in link for link in links)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
