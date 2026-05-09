"""
Run the Phase 1.1 Fetcher to populate data folders with scraped content.
"""

import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.dirname(__file__))

from web_scraper import WebScraper
from document_downloader import DocumentDownloader
from config import get_config
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Run the fetcher to scrape and download data."""
    logger.info("Starting Phase 1.1 Fetcher...")
    
    # Load configuration
    config = get_config()
    
    # Initialize scraper
    scraper = WebScraper(
        user_agent=config.user_agent,
        request_delay=config.request_delay,
        timeout=config.timeout
    )
    
    # Initialize downloader
    downloader = DocumentDownloader(
        output_dir=config.download_dir,
        timeout=config.timeout,
        user_agent=config.user_agent
    )
    
    # Scrape URLs
    logger.info(f"Scraping {len(config.urls)} URLs...")
    scraped_results = []
    
    for url in config.urls:
        logger.info(f"Scraping: {url}")
        result = scraper.scrape_url(url)
        scraped_results.append(result)
        
        if result.error:
            logger.error(f"Error scraping {url}: {result.error}")
        else:
            logger.info(f"Successfully scraped: {result.scheme_name}")
    
    # Save HTML files
    html_output_dir = config.output_dir
    os.makedirs(html_output_dir, exist_ok=True)
    
    for result in scraped_results:
        if result.html and result.scheme_name:
            # Create safe filename
            scheme_name_safe = result.scheme_name.replace(' ', '_').replace('/', '_')
            filename = f"{scheme_name_safe}.html"
            filepath = os.path.join(html_output_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(result.html)
            
            logger.info(f"Saved HTML: {filepath}")
    
    # Download documents (PDF links would be extracted from HTML)
    # For now, we'll just save the HTML files
    logger.info(f"HTML files saved to: {html_output_dir}")
    logger.info(f"Phase 1.1 Fetcher complete!")


if __name__ == "__main__":
    main()
