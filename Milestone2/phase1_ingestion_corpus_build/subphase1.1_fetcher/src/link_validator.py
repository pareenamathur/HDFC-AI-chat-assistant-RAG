"""
Link Validator Module
Validates URL accessibility before processing in the fetcher pipeline.
"""

import requests
from typing import Dict, List, Tuple
from dataclasses import dataclass
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Data class to hold validation results."""
    url: str
    is_valid: bool
    status_code: int
    error: str = None
    response_time_ms: float = 0.0


class LinkValidator:
    """Validates URLs for accessibility and returns detailed results."""
    
    def __init__(self, timeout: int = 10, user_agent: str = None):
        """
        Initialize the link validator.
        
        Args:
            timeout: Request timeout in seconds
            user_agent: Custom User-Agent string
        """
        self.timeout = timeout
        self.headers = {
            'User-Agent': user_agent or (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/91.0.4472.124 Safari/537.36'
            )
        }
    
    def validate_url(self, url: str) -> ValidationResult:
        """
        Validate a single URL.
        
        Args:
            url: URL to validate
            
        Returns:
            ValidationResult object with validation details
        """
        try:
            import time
            start_time = time.time()
            
            response = requests.get(
                url,
                headers=self.headers,
                timeout=self.timeout,
                allow_redirects=True
            )
            
            response_time = (time.time() - start_time) * 1000
            
            is_valid = response.status_code == 200
            
            if not is_valid:
                error_msg = f"HTTP {response.status_code}"
            else:
                error_msg = None
            
            return ValidationResult(
                url=url,
                is_valid=is_valid,
                status_code=response.status_code,
                error=error_msg,
                response_time_ms=response_time
            )
            
        except requests.exceptions.Timeout:
            logger.error(f"Timeout while validating {url}")
            return ValidationResult(
                url=url,
                is_valid=False,
                status_code=None,
                error="Request timeout"
            )
        except requests.exceptions.ConnectionError:
            logger.error(f"Connection error while validating {url}")
            return ValidationResult(
                url=url,
                is_valid=False,
                status_code=None,
                error="Connection error"
            )
        except Exception as e:
            logger.error(f"Unexpected error validating {url}: {str(e)}")
            return ValidationResult(
                url=url,
                is_valid=False,
                status_code=None,
                error=str(e)
            )
    
    def validate_urls(self, urls: List[str]) -> List[ValidationResult]:
        """
        Validate multiple URLs.
        
        Args:
            urls: List of URLs to validate
            
        Returns:
            List of ValidationResult objects
        """
        results = []
        
        for url in urls:
            logger.info(f"Validating: {url}")
            result = self.validate_url(url)
            results.append(result)
            
            if result.is_valid:
                logger.info(f"[VALID] {url} ({result.response_time_ms:.2f}ms)")
            else:
                logger.warning(f"[INVALID] {url} - {result.error}")
        
        return results
    
    def get_valid_urls(self, urls: List[str]) -> Tuple[List[str], List[ValidationResult]]:
        """
        Get only valid URLs from a list.
        
        Args:
            urls: List of URLs to validate
            
        Returns:
            Tuple of (valid_urls, all_results)
        """
        results = self.validate_urls(urls)
        valid_urls = [r.url for r in results if r.is_valid]
        return valid_urls, results
    
    def generate_report(self, results: List[ValidationResult]) -> str:
        """
        Generate a validation report.
        
        Args:
            results: List of ValidationResult objects
            
        Returns:
            Formatted report string
        """
        total = len(results)
        valid = sum(1 for r in results if r.is_valid)
        invalid = total - valid
        
        report = [
            "=" * 60,
            "Link Validation Report",
            "=" * 60,
            f"Total URLs: {total}",
            f"Valid: {valid}",
            f"Invalid: {invalid}",
            "=" * 60,
            ""
        ]
        
        for result in results:
            status = "[VALID]" if result.is_valid else "[INVALID]"
            report.append(f"{status}: {result.url}")
            if not result.is_valid:
                report.append(f"  Error: {result.error}")
            else:
                report.append(f"  Status: {result.status_code} | Time: {result.response_time_ms:.2f}ms")
            report.append("")
        
        return "\n".join(report)


if __name__ == "__main__":
    # Load URLs from configuration
    try:
        from config import get_config
        config = get_config()
        test_urls = config.urls
        print(f"Loaded {len(test_urls)} URLs from configuration")
    except Exception as e:
        print(f"Error loading config: {e}")
        print("Using test URLs instead")
        test_urls = [
            "https://groww.in/mutual-funds/hdfc-nifty50-equal-weight-index-fund-direct-growth",
            "https://groww.in/mutual-funds/hdfc-nifty-top-20-equal-weight-index-fund-direct-growth",
        ]
    
    validator = LinkValidator()
    results = validator.validate_urls(test_urls)
    print(validator.generate_report(results))
