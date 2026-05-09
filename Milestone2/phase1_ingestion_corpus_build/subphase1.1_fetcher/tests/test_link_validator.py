"""
Unit tests for link_validator module
"""

import pytest
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from link_validator import LinkValidator, ValidationResult


class TestLinkValidator:
    """Test cases for LinkValidator class."""
    
    @pytest.fixture
    def validator(self):
        """Create a LinkValidator instance for testing."""
        return LinkValidator(timeout=10)
    
    def test_initialization(self, validator):
        """Test validator initialization."""
        assert validator.timeout == 10
        assert validator.headers is not None
        assert 'User-Agent' in validator.headers
    
    def test_validate_valid_url(self, validator):
        """Test validation of a valid URL."""
        # Using a reliable test URL
        result = validator.validate_url("https://httpbin.org/status/200")
        
        assert isinstance(result, ValidationResult)
        assert result.url == "https://httpbin.org/status/200"
        assert result.is_valid == True
        assert result.status_code == 200
    
    def test_validate_invalid_url(self, validator):
        """Test validation of an invalid URL."""
        result = validator.validate_url("https://httpbin.org/status/404")
        
        assert isinstance(result, ValidationResult)
        assert result.url == "https://httpbin.org/status/404"
        assert result.is_valid == False
        assert result.status_code == 404
        assert result.error is not None
    
    def test_validate_timeout(self, validator):
        """Test validation with timeout."""
        # Using a URL that will timeout
        slow_validator = LinkValidator(timeout=1)
        result = slow_validator.validate_url("https://httpbin.org/delay/5")
        
        assert isinstance(result, ValidationResult)
        assert result.is_valid == False
        assert result.error == "Request timeout"
    
    def test_validate_multiple_urls(self, validator):
        """Test validation of multiple URLs."""
        urls = [
            "https://httpbin.org/status/200",
            "https://httpbin.org/status/404",
        ]
        
        results = validator.validate_urls(urls)
        
        assert len(results) == 2
        assert results[0].is_valid == True
        assert results[1].is_valid == False
    
    def test_get_valid_urls(self, validator):
        """Test filtering valid URLs."""
        urls = [
            "https://httpbin.org/status/200",
            "https://httpbin.org/status/404",
        ]
        
        valid_urls, all_results = validator.get_valid_urls(urls)
        
        assert len(valid_urls) == 1
        assert valid_urls[0] == "https://httpbin.org/status/200"
        assert len(all_results) == 2
    
    def test_generate_report(self, validator):
        """Test report generation."""
        urls = ["https://httpbin.org/status/200"]
        results = validator.validate_urls(urls)
        
        report = validator.generate_report(results)
        
        assert isinstance(report, str)
        assert "Link Validation Report" in report
        assert "Total URLs" in report
        assert "Valid" in report


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
