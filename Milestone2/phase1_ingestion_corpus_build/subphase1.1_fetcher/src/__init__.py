"""
Sub-phase 1.1 - Fetcher
Web scraping and document downloading for HDFC mutual fund schemes.
"""

from .link_validator import LinkValidator, ValidationResult
from .web_scraper import WebScraper, ScrapedContent
from .document_downloader import DocumentDownloader, DownloadedDocument
from .config import ConfigManager, FetcherConfig, get_config

__all__ = [
    'LinkValidator',
    'ValidationResult',
    'WebScraper',
    'ScrapedContent',
    'DocumentDownloader',
    'DownloadedDocument',
    'ConfigManager',
    'FetcherConfig',
    'get_config'
]
