"""
HTML Extractor Module
Extracts content from HTML files scraped by the fetcher.
"""

from bs4 import BeautifulSoup
from typing import Dict, List, Optional
import logging
from dataclasses import dataclass
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class HTMLExtractedContent:
    """Data class to hold extracted content from HTML."""
    url: str
    html: str
    text: str
    scheme_name: str
    metadata: Dict[str, str]
    structured_data: Dict[str, str]
    document_links: List[Dict[str, str]]
    error: str = None


class HTMLExtractor:
    """Extracts content from HTML files."""
    
    def __init__(self):
        """Initialize the HTML extractor."""
        pass
    
    def extract_html(self, html: str, url: str) -> HTMLExtractedContent:
        """
        Extract content from HTML string.
        
        Args:
            html: HTML string
            url: Source URL
            
        Returns:
            HTMLExtractedContent object
        """
        try:
            logger.info(f"Extracting from HTML: {url}")
            
            soup = BeautifulSoup(html, 'html.parser')
            
            # Extract text
            text = soup.get_text(separator=' ', strip=True)
            
            # Extract scheme name
            scheme_name = self._extract_scheme_name(soup, url)
            
            # Extract metadata
            metadata = self._extract_metadata(soup)
            
            # Extract structured data
            structured_data = self._extract_structured_data(soup)
            
            # Extract document links
            document_links = self._extract_document_links(soup, url)
            
            logger.info(f"Extracted {len(text)} characters from HTML")
            
            return HTMLExtractedContent(
                url=url,
                html=html,
                text=text,
                scheme_name=scheme_name,
                metadata=metadata,
                structured_data=structured_data,
                document_links=document_links
            )
            
        except Exception as e:
            logger.error(f"Error extracting HTML: {str(e)}")
            return HTMLExtractedContent(
                url=url,
                html=html,
                text="",
                scheme_name="",
                metadata={},
                structured_data={},
                document_links=[],
                error=str(e)
            )
    
    def _extract_scheme_name(self, soup: BeautifulSoup, url: str) -> str:
        """
        Extract scheme name from HTML.
        
        Args:
            soup: BeautifulSoup object
            url: Source URL
            
        Returns:
            Scheme name
        """
        # Try title tag
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.get_text(strip=True)
            # Remove " - Groww" suffix
            scheme_name = title.replace(" - Groww", "").strip()
            return scheme_name
        
        # Try h1 tag
        h1_tag = soup.find('h1')
        if h1_tag:
            return h1_tag.get_text(strip=True)
        
        # Fallback to URL
        return "Unknown Scheme"
    
    def _extract_metadata(self, soup: BeautifulSoup) -> Dict[str, str]:
        """
        Extract metadata from HTML.
        
        Args:
            soup: BeautifulSoup object
            
        Returns:
            Dictionary of metadata
        """
        metadata = {}
        
        # Extract meta tags
        for meta in soup.find_all('meta'):
            if meta.get('name'):
                metadata[meta.get('name')] = meta.get('content', '')
        
        return metadata
    
    def _extract_structured_data(self, soup: BeautifulSoup) -> Dict[str, str]:
        """
        Extract structured data from HTML.
    
        Args:
            soup: BeautifulSoup object
    
        Returns:
            Dictionary with structured data
        """
        structured_data = {}
        text = soup.get_text(separator=' ', strip=True)
    
        # Extract expense ratio — look for "Expense ratio X.XX%" pattern
        expense_match = re.search(r'expense\s*ratio\s+([0-9]+\.?[0-9]*\s*%)', text, re.IGNORECASE)
        if expense_match:
            structured_data['expense_ratio'] = expense_match.group(1).strip()
    
        # Extract exit load — look for percentage-based patterns near "Exit Load" / "exit load"
        # Avoid matching dates like "01 Jun 2018" by requiring a % sign or a clear percentage pattern
        exit_load_patterns = [
            r'exit\s*load[^.]*?([0-9]+\.?[0-9]*\s*%)',  # "exit load of 1%"
            r'exit\s*load[^.]*?Nil',                      # "exit load Nil"
        ]
        for pattern in exit_load_patterns:
            exit_match = re.search(pattern, text, re.IGNORECASE)
            if exit_match:
                val = exit_match.group(1).strip() if exit_match.lastindex else 'Nil'
                structured_data['exit_load'] = val
                break
    
        # Fallback: if no % found, grab the full exit load sentence
        if 'exit_load' not in structured_data:
            exit_sentence = re.search(r'exit\s*load[:\s]+([^.]+)', text, re.IGNORECASE)
            if exit_sentence:
                structured_data['exit_load'] = exit_sentence.group(1).strip()
    
        # Extract NAV — "NAV: DD Mon YY ₹XXX.XX"
        nav_match = re.search(r'nav[:\s]+(?:\d{1,2}\s+\w{3}\s+\'?\d{2,4}[\s.]*)?(?:₹?\s*)?([0-9,]+\.?[0-9]*)', text, re.IGNORECASE)
        if nav_match:
            structured_data['nav'] = nav_match.group(1).strip()
    
        # Extract AUM / Fund size
        aum_match = re.search(r'(?:fund\s*size|aum)[:\s]+(?:₹\s*)?([0-9,]+\.?[0-9]*\s*Cr)', text, re.IGNORECASE)
        if aum_match:
            structured_data['aum'] = aum_match.group(1).strip()
    
        # Extract SIP minimum amount
        sip_match = re.search(r'min\.?\s*for\s*sip[:\s]+(?:₹\s*)?([0-9,]+)', text, re.IGNORECASE)
        if sip_match:
            structured_data['sip_minimum'] = sip_match.group(1).strip()
    
        # Extract risk level
        risk_match = re.search(r'(very\s*high\s*risk|high\s*risk|moderately\s*high\s*risk|moderate\s*risk|low\s*risk|very\s*low\s*risk)', text, re.IGNORECASE)
        if risk_match:
            structured_data['risk_level'] = risk_match.group(1).strip().title()
    
        # Extract category / fund type
        category_match = re.search(r'(hybrid\s+dynamic\s+asset\s+allocation|equity\s+large\s+cap|equity\s+flexi\s+cap|equity\s+mid\s+cap|equity\s+small\s+cap|equity\s+multi\s+cap|debt\s+corporate\s+bond|debt\s+short\s+(?:term|duration)|fund\s+of\s+fund|index\s+fund|sectoral)', text, re.IGNORECASE)
        if category_match:
            structured_data['category'] = category_match.group(1).strip().title()
    
        # Extract benchmark
        benchmark_match = re.search(r'benchmark\s+([A-Z][A-Za-z0-9\s&%+(]+?)(?:\s+Scheme|\s+Fund|\s*$)', text)
        if benchmark_match:
            structured_data['benchmark'] = benchmark_match.group(1).strip()
    
        return structured_data
    
    def _extract_document_links(self, soup: BeautifulSoup, base_url: str) -> List[Dict[str, str]]:
        """
        Extract document links from HTML.
        
        Args:
            soup: BeautifulSoup object
            base_url: Base URL for resolving relative links
            
        Returns:
            List of document link dictionaries
        """
        document_links = []
        
        for link in soup.find_all('a', href=True):
            href = link['href']
            link_text = link.get_text().lower()
            
            # Determine document type
            doc_type = 'other'
            if 'factsheet' in link_text or 'fact-sheet' in href.lower():
                doc_type = 'factsheet'
            elif 'kim' in link_text or 'key information' in href.lower():
                doc_type = 'kim'
            elif 'sid' in link_text or 'scheme information' in href.lower():
                doc_type = 'sid'
            
            if doc_type != 'other' or href.lower().endswith('.pdf'):
                document_links.append({
                    'url': href,
                    'type': doc_type,
                    'text': link.get_text(strip=True)
                })
        
        return document_links


if __name__ == "__main__":
    # Example usage
    extractor = HTMLExtractor()
    
    html = """
    <html>
        <head><title>HDFC Nifty50 Fund - Groww</title></head>
        <body>
            <h1>HDFC Nifty50 Fund</h1>
            <p>Expense Ratio: 0.5%</p>
            <a href="/factsheet.pdf">Download Factsheet</a>
        </body>
    </html>
    """
    
    result = extractor.extract_html(html, "https://example.com")
    print(f"Scheme: {result.scheme_name}")
    print(f"Structured data: {result.structured_data}")
    print(f"Document links: {result.document_links}")
