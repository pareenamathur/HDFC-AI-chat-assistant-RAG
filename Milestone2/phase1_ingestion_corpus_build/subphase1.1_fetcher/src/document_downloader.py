"""
Document Downloader Module
Downloads linked factsheets, KIMs, SIDs from Groww pages with checksum validation.
"""

import requests
import hashlib
import os
from typing import Dict, List, Optional
import logging
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class DownloadedDocument:
    """Data class to hold downloaded document info."""
    url: str
    filepath: str
    file_type: str  # factsheet, kim, sid, other
    checksum: str
    size_bytes: int
    error: str = None


class DocumentDownloader:
    """Downloads documents from Groww pages with checksum validation."""
    
    def __init__(
        self,
        output_dir: str = "./downloads",
        timeout: int = 60,
        user_agent: str = None
    ):
        """
        Initialize the document downloader.
        
        Args:
            output_dir: Directory to save downloaded documents
            timeout: Download timeout in seconds
            user_agent: Custom User-Agent string
        """
        self.output_dir = output_dir
        self.timeout = timeout
        self.headers = {
            'User-Agent': user_agent or (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/91.0.4472.124 Safari/537.36'
            )
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
        # Create output directory
        os.makedirs(self.output_dir, exist_ok=True)
    
    def download_document(self, url: str, filename: str = None) -> DownloadedDocument:
        """
        Download a single document.
        
        Args:
            url: URL of the document
            filename: Optional custom filename
            
        Returns:
            DownloadedDocument object
        """
        try:
            logger.info(f"Downloading: {url}")
            
            response = self.session.get(
                url,
                timeout=self.timeout,
                stream=True
            )
            
            if response.status_code != 200:
                logger.warning(f"Failed to download {url}: HTTP {response.status_code}")
                return DownloadedDocument(
                    url=url,
                    filepath="",
                    file_type="unknown",
                    checksum="",
                    size_bytes=0,
                    error=f"HTTP {response.status_code}"
                )
            
            # Determine filename if not provided
            if not filename:
                filename = self._get_filename_from_url(url)
            
            filepath = os.path.join(self.output_dir, filename)
            
            # Download with streaming
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            # Calculate checksum
            checksum = self._calculate_checksum(filepath)
            
            # Get file size
            size_bytes = os.path.getsize(filepath)
            
            # Determine file type
            file_type = self._determine_file_type(filename, url)
            
            logger.info(f"✓ Downloaded: {filename} ({size_bytes} bytes)")
            
            return DownloadedDocument(
                url=url,
                filepath=filepath,
                file_type=file_type,
                checksum=checksum,
                size_bytes=size_bytes
            )
            
        except requests.exceptions.Timeout:
            logger.error(f"Timeout while downloading {url}")
            return DownloadedDocument(
                url=url,
                filepath="",
                file_type="unknown",
                checksum="",
                size_bytes=0,
                error="Request timeout"
            )
        except Exception as e:
            logger.error(f"Error downloading {url}: {str(e)}")
            return DownloadedDocument(
                url=url,
                filepath="",
                file_type="unknown",
                checksum="",
                size_bytes=0,
                error=str(e)
            )
    
    def extract_and_download_documents(self, html_content: str, base_url: str, scheme_name: str) -> List[DownloadedDocument]:
        """
        Extract document links from HTML and download them.
        
        Args:
            html_content: HTML content of the page
            base_url: Base URL of the page
            scheme_name: Name of the scheme for folder organization
            
        Returns:
            List of DownloadedDocument objects
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Create scheme-specific directory
        scheme_dir = os.path.join(self.output_dir, scheme_name.replace(" ", "_"))
        os.makedirs(scheme_dir, exist_ok=True)
        
        # Update output directory for this scheme
        original_output_dir = self.output_dir
        self.output_dir = scheme_dir
        
        # Find document links
        document_links = self._find_document_links(soup, base_url)
        
        logger.info(f"Found {len(document_links)} document links for {scheme_name}")
        
        # Download documents
        results = []
        for link_info in document_links:
            result = self.download_document(link_info['url'], link_info.get('filename'))
            result.file_type = link_info.get('type', 'other')
            results.append(result)
        
        # Restore original output directory
        self.output_dir = original_output_dir
        
        return results
    
    def _find_document_links(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        """
        Find document links in the HTML.
        
        Args:
            soup: BeautifulSoup object
            base_url: Base URL for resolving relative links
            
        Returns:
            List of dictionaries with url, type, and filename
        """
        document_links = []
        
        # Keywords to identify document types
        keywords = {
            'factsheet': ['factsheet', 'fact-sheet', 'fact sheet'],
            'kim': ['kim', 'key information memorandum'],
            'sid': ['sid', 'scheme information document', 'scheme information']
        }
        
        # Find all links
        for link in soup.find_all('a', href=True):
            href = link['href']
            link_text = link.get_text().lower()
            
            # Convert relative URLs to absolute
            if href.startswith('/'):
                absolute_url = urljoin(base_url, href)
            elif href.startswith('http'):
                absolute_url = href
            else:
                continue
            
            # Determine document type
            doc_type = 'other'
            for type_name, type_keywords in keywords.items():
                if any(keyword in link_text or keyword in href.lower() for keyword in type_keywords):
                    doc_type = type_name
                    break
            
            # Only include PDF links or document-like links
            if doc_type != 'other' or href.lower().endswith('.pdf'):
                filename = self._get_filename_from_url(absolute_url)
                document_links.append({
                    'url': absolute_url,
                    'type': doc_type,
                    'filename': filename
                })
        
        return document_links
    
    def _get_filename_from_url(self, url: str) -> str:
        """
        Extract filename from URL.
        
        Args:
            url: URL string
            
        Returns:
            Filename
        """
        parsed = urlparse(url)
        filename = os.path.basename(parsed.path)
        
        if not filename or '.' not in filename:
            # Generate filename from URL if not present
            filename = f"document_{hash(url)}.pdf"
        
        return filename
    
    def _calculate_checksum(self, filepath: str) -> str:
        """
        Calculate SHA-256 checksum of a file.
        
        Args:
            filepath: Path to the file
            
        Returns:
            Hexadecimal checksum string
        """
        sha256_hash = hashlib.sha256()
        
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        
        return sha256_hash.hexdigest()
    
    def _determine_file_type(self, filename: str, url: str) -> str:
        """
        Determine file type based on filename and URL.
        
        Args:
            filename: Filename
            url: URL
            
        Returns:
            File type string
        """
        lower_name = filename.lower()
        lower_url = url.lower()
        
        if 'factsheet' in lower_name or 'fact-sheet' in lower_url:
            return 'factsheet'
        elif 'kim' in lower_name or 'key information' in lower_url:
            return 'kim'
        elif 'sid' in lower_name or 'scheme information' in lower_url:
            return 'sid'
        elif lower_name.endswith('.pdf'):
            return 'pdf'
        else:
            return 'other'
    
    def validate_checksum(self, filepath: str, expected_checksum: str) -> bool:
        """
        Validate file checksum.
        
        Args:
            filepath: Path to the file
            expected_checksum: Expected checksum
            
        Returns:
            True if checksum matches, False otherwise
        """
        actual_checksum = self._calculate_checksum(filepath)
        return actual_checksum == expected_checksum


if __name__ == "__main__":
    # Example usage
    downloader = DocumentDownloader(output_dir="./test_downloads")
    
    # Test with a sample PDF URL
    test_url = "https://example.com/factsheet.pdf"
    result = downloader.download_document(test_url)
    
    if result.error:
        print(f"Error: {result.error}")
    else:
        print(f"Downloaded: {result.filepath}")
        print(f"Checksum: {result.checksum}")
        print(f"Type: {result.file_type}")
