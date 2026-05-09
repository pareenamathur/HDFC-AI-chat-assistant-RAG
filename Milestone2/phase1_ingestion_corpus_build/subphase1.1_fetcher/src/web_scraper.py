"""
Web Scraper Module
Crawls whitelisted Groww URLs and extracts HTML content with bot detection avoidance.
"""

import requests
from bs4 import BeautifulSoup
from typing import Dict, List, Optional
import time
import logging
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ScrapedContent:
    """Data class to hold scraped content."""
    url: str
    html: str
    status_code: int
    title: str = None
    scheme_name: str = None
    links: List[str] = None
    error: str = None


class WebScraper:
    """Web scraper with throttling and custom headers to avoid bot detection."""
    
    def __init__(
        self,
        user_agent: str = None,
        request_delay: float = 2.0,
        timeout: int = 30
    ):
        """
        Initialize the web scraper.
        
        Args:
            user_agent: Custom User-Agent string
            request_delay: Delay between requests in seconds
            timeout: Request timeout in seconds
        """
        self.request_delay = request_delay
        self.timeout = timeout
        self.headers = {
            'User-Agent': user_agent or (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/91.0.4472.124 Safari/537.36'
            ),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
    
    def scrape_url(self, url: str) -> ScrapedContent:
        """
        Scrape a single URL.
        
        Args:
            url: URL to scrape
            
        Returns:
            ScrapedContent object with scraped data
        """
        try:
            logger.info(f"Scraping: {url}")
            
            response = self.session.get(
                url,
                timeout=self.timeout,
                allow_redirects=True
            )
            
            if response.status_code != 200:
                logger.warning(f"Failed to scrape {url}: HTTP {response.status_code}")
                return ScrapedContent(
                    url=url,
                    html="",
                    status_code=response.status_code,
                    error=f"HTTP {response.status_code}"
                )
            
            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract title
            title = soup.find('title')
            title_text = title.get_text(strip=True) if title else ""
            
            # Extract scheme name from title (Groww format)
            scheme_name = self._extract_scheme_name(title_text, url)
            
            # Extract all links
            links = self._extract_links(soup, url)
            
            logger.info(f"✓ Scraped: {url} - {scheme_name}")
            
            return ScrapedContent(
                url=url,
                html=response.text,
                status_code=response.status_code,
                title=title_text,
                scheme_name=scheme_name,
                links=links
            )
            
        except requests.exceptions.Timeout:
            logger.error(f"Timeout while scraping {url}")
            return ScrapedContent(
                url=url,
                html="",
                status_code=None,
                error="Request timeout"
            )
        except requests.exceptions.ConnectionError:
            logger.error(f"Connection error while scraping {url}")
            return ScrapedContent(
                url=url,
                html="",
                status_code=None,
                error="Connection error"
            )
        except Exception as e:
            logger.error(f"Unexpected error scraping {url}: {str(e)}")
            return ScrapedContent(
                url=url,
                html="",
                status_code=None,
                error=str(e)
            )
    
    def scrape_urls(self, urls: List[str]) -> List[ScrapedContent]:
        """
        Scrape multiple URLs with throttling.
        
        Args:
            urls: List of URLs to scrape
            
        Returns:
            List of ScrapedContent objects
        """
        results = []
        
        for i, url in enumerate(urls):
            if i > 0:
                logger.info(f"Waiting {self.request_delay}s before next request...")
                time.sleep(self.request_delay)
            
            result = self.scrape_url(url)
            results.append(result)
        
        return results
    
    def _extract_scheme_name(self, title: str, url: str) -> str:
        """
        Extract scheme name from title or URL.
        
        Args:
            title: Page title
            url: Page URL
            
        Returns:
            Extracted scheme name
        """
        if title:
            # Groww title format: "HDFC Nifty50 Equal Weight Index Fund - Groww"
            # Remove " - Groww" suffix
            scheme_name = title.replace(" - Groww", "").strip()
            return scheme_name
        
        # Fallback: extract from URL
        # URL format: https://groww.in/mutual-funds/hdfc-nifty50-equal-weight-index-fund-direct-growth
        parts = url.split("/mutual-funds/")
        if len(parts) > 1:
            scheme_part = parts[1].replace("-direct-growth", "").replace("-", " ").title()
            return scheme_part
        
        return "Unknown Scheme"
    
    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """
        Extract all links from the page.
        
        Args:
            soup: BeautifulSoup object
            base_url: Base URL for resolving relative links
            
        Returns:
            List of absolute URLs
        """
        links = []
        
        for link in soup.find_all('a', href=True):
            href = link['href']
            
            # Convert relative URLs to absolute
            if href.startswith('/'):
                # Extract base domain
                from urllib.parse import urljoin
                absolute_url = urljoin(base_url, href)
                links.append(absolute_url)
            elif href.startswith('http'):
                links.append(href)
        
        return links
    
    def save_html(self, content: ScrapedContent, output_dir: str) -> str:
        """
        Save scraped HTML to file.
        
        Args:
            content: ScrapedContent object
            output_dir: Directory to save HTML files
            
        Returns:
            Path to saved file
        """
        import os
        
        if not content.html:
            logger.warning(f"No HTML content to save for {content.url}")
            return None
        
        # Create safe filename from scheme name
        safe_name = content.scheme_name.replace(" ", "_").replace("/", "_")
        filename = f"{safe_name}.html"
        filepath = os.path.join(output_dir, filename)
        
        os.makedirs(output_dir, exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content.html)
        
        logger.info(f"Saved HTML to: {filepath}")
        return filepath


if __name__ == "__main__":
    # Example usage
    scraper = WebScraper(request_delay=2.0)
    
    test_urls = [
        "https://groww.in/mutual-funds/hdfc-nifty50-equal-weight-index-fund-direct-growth",
    ]
    
    results = scraper.scrape_urls(test_urls)
    
    for result in results:
        if result.error:
            print(f"Error: {result.url} - {result.error}")
        else:
            print(f"Success: {result.scheme_name}")
            print(f"  Links found: {len(result.links)}")
