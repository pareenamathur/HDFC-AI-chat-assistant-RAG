"""
Unit tests for document_downloader module
"""

import pytest
import sys
import os
import tempfile

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from document_downloader import DocumentDownloader, DownloadedDocument


class TestDocumentDownloader:
    """Test cases for DocumentDownloader class."""
    
    @pytest.fixture
    def downloader(self):
        """Create a DocumentDownloader instance for testing."""
        temp_dir = tempfile.mkdtemp()
        return DocumentDownloader(output_dir=temp_dir, timeout=30)
    
    def test_initialization(self, downloader):
        """Test downloader initialization."""
        assert downloader.output_dir is not None
        assert downloader.timeout == 30
        assert downloader.headers is not None
        assert 'User-Agent' in downloader.headers
    
    def test_get_filename_from_url(self, downloader):
        """Test filename extraction from URL."""
        url = "https://example.com/documents/factsheet.pdf"
        filename = downloader._get_filename_from_url(url)
        
        assert filename == "factsheet.pdf"
    
    def test_determine_file_type(self, downloader):
        """Test file type determination."""
        # Test factsheet
        file_type = downloader._determine_file_type("factsheet.pdf", "https://example.com/factsheet")
        assert file_type == "factsheet"
        
        # Test KIM
        file_type = downloader._determine_file_type("kim.pdf", "https://example.com/kim")
        assert file_type == "kim"
        
        # Test SID
        file_type = downloader._determine_file_type("sid.pdf", "https://example.com/sid")
        assert file_type == "sid"
    
    def test_calculate_checksum(self, downloader):
        """Test checksum calculation."""
        # Create a temporary file
        temp_file = os.path.join(downloader.output_dir, "test.txt")
        with open(temp_file, 'w') as f:
            f.write("test content")
        
        checksum = downloader._calculate_checksum(temp_file)
        
        assert isinstance(checksum, str)
        assert len(checksum) == 64  # SHA-256 produces 64 hex characters
        
        # Clean up
        os.remove(temp_file)
    
    def test_validate_checksum(self, downloader):
        """Test checksum validation."""
        # Create a temporary file
        temp_file = os.path.join(downloader.output_dir, "test.txt")
        with open(temp_file, 'w') as f:
            f.write("test content")
        
        # Calculate correct checksum
        correct_checksum = downloader._calculate_checksum(temp_file)
        
        # Test with correct checksum
        assert downloader.validate_checksum(temp_file, correct_checksum) == True
        
        # Test with incorrect checksum
        assert downloader.validate_checksum(temp_file, "wrongchecksum") == False
        
        # Clean up
        os.remove(temp_file)
    
    def test_find_document_links(self, downloader):
        """Test document link extraction from HTML."""
        html = """
        <html>
            <body>
                <a href="/factsheet.pdf">Download Factsheet</a>
                <a href="/kim.pdf">KIM Document</a>
                <a href="/sid.pdf">Scheme Information</a>
                <a href="/other.html">Other Page</a>
            </body>
        </html>
        """
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        
        links = downloader._find_document_links(soup, "https://example.com")
        
        assert len(links) >= 3  # Should find at least the PDF links
        assert any(link['type'] == 'factsheet' for link in links)
        assert any(link['type'] == 'kim' for link in links)
        assert any(link['type'] == 'sid' for link in links)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
