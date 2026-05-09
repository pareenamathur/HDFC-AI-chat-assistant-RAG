"""
PDF Extractor Module
Extracts text and structured data from PDF documents with fallback to OCR.
"""

import fitz  # PyMuPDF
from typing import Dict, List, Optional, Any
import logging
from dataclasses import dataclass
import re
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ExtractedContent:
    """Data class to hold extracted content from PDF."""
    filepath: str
    text: str
    pages: int
    metadata: Dict[str, Any]
    structured_data: Dict[str, Any]
    sections: Dict[str, str]
    tables: List[Dict[str, Any]]
    error: str = None


class PDFExtractor:
    """Extracts text and structured data from PDF documents."""
    
    def __init__(self, use_ocr_fallback: bool = True):
        """
        Initialize the PDF extractor.
        
        Args:
            use_ocr_fallback: Whether to use OCR for scanned PDFs
        """
        self.use_ocr_fallback = use_ocr_fallback
        self.ocr_available = self._check_ocr_available()
    
    def _check_ocr_available(self) -> bool:
        """Check if OCR (Tesseract) is available."""
        try:
            import pytesseract
            from PIL import Image
            return True
        except ImportError:
            logger.warning("OCR not available. Install pytesseract and Pillow for OCR fallback.")
            return False
    
    def extract_pdf(self, filepath: str) -> ExtractedContent:
        """
        Extract content from a PDF file.
        
        Args:
            filepath: Path to the PDF file
            
        Returns:
            ExtractedContent object with extracted data
        """
        try:
            logger.info(f"Extracting from: {filepath}")
            
            if not os.path.exists(filepath):
                return ExtractedContent(
                    filepath=filepath,
                    text="",
                    pages=0,
                    metadata={},
                    structured_data={},
                    sections={},
                    tables=[],
                    error="File not found"
                )
            
            # Try PyMuPDF first
            doc = fitz.open(filepath)
            
            # Extract text
            text = ""
            for page in doc:
                text += page.get_text()
            
            # Check if text extraction was successful
            if len(text.strip()) < 100:
                logger.warning(f"Low text extraction from {filepath}, might be scanned")
                if self.use_ocr_fallback and self.ocr_available:
                    logger.info("Attempting OCR fallback...")
                    text = self._extract_with_ocr(filepath)
            
            # Extract metadata
            metadata = {
                'title': doc.metadata.get('title', ''),
                'author': doc.metadata.get('author', ''),
                'subject': doc.metadata.get('subject', ''),
                'creator': doc.metadata.get('creator', ''),
                'producer': doc.metadata.get('producer', ''),
                'page_count': len(doc)
            }
            
            # Extract structured data
            structured_data = self._extract_structured_data(text)
            
            # Extract sections
            sections = self._extract_sections(text)
            
            # Extract tables
            tables = self._extract_tables(doc)
            
            doc.close()
            
            logger.info(f"Extracted {len(text)} characters from {filepath}")
            
            return ExtractedContent(
                filepath=filepath,
                text=text,
                pages=len(doc),
                metadata=metadata,
                structured_data=structured_data,
                sections=sections,
                tables=tables
            )
            
        except Exception as e:
            logger.error(f"Error extracting from {filepath}: {str(e)}")
            return ExtractedContent(
                filepath=filepath,
                text="",
                pages=0,
                metadata={},
                structured_data={},
                sections={},
                tables=[],
                error=str(e)
            )
    
    def _extract_with_ocr(self, filepath: str) -> str:
        """
        Extract text from PDF using OCR (Tesseract).
        
        Args:
            filepath: Path to the PDF file
            
        Returns:
            Extracted text
        """
        try:
            import pytesseract
            from PIL import Image
            import io
            
            doc = fitz.open(filepath)
            text = ""
            
            for page_num, page in enumerate(doc):
                # Convert page to image
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                img_data = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_data))
                
                # OCR the image
                page_text = pytesseract.image_to_string(img)
                text += f"\n--- Page {page_num + 1} ---\n{page_text}"
            
            doc.close()
            return text
            
        except Exception as e:
            logger.error(f"OCR extraction failed: {str(e)}")
            return ""
    
    def _extract_structured_data(self, text: str) -> Dict[str, Any]:
        """
        Extract structured financial data from text.
        
        Args:
            text: Extracted text
            
        Returns:
            Dictionary with structured data
        """
        structured_data = {}
        
        # Extract expense ratio
        expense_ratio_match = re.search(r'expense\s*ratio[:\s]*([0-9.]+%?)', text, re.IGNORECASE)
        if expense_ratio_match:
            structured_data['expense_ratio'] = expense_ratio_match.group(1)
        
        # Extract exit load
        exit_load_match = re.search(r'exit\s*load[:\s]*([0-9.]+%?)', text, re.IGNORECASE)
        if exit_load_match:
            structured_data['exit_load'] = exit_load_match.group(1)
        
        # Extract SIP amount
        sip_match = re.search(r'sip\s*(?:amount|minimum)[:\s]*(?:Rs\.?\s*)?([0-9,]+)', text, re.IGNORECASE)
        if sip_match:
            structured_data['sip_amount'] = sip_match.group(1)
        
        # Extract benchmark
        benchmark_match = re.search(r'benchmark[:\s]*([^\n]+)', text, re.IGNORECASE)
        if benchmark_match:
            structured_data['benchmark'] = benchmark_match.group(1).strip()
        
        # Extract riskometer
        risk_match = re.search(r'riskometer[:\s]*([^\n]+)', text, re.IGNORECASE)
        if risk_match:
            structured_data['riskometer'] = risk_match.group(1).strip()
        
        return structured_data
    
    def _extract_sections(self, text: str) -> Dict[str, str]:
        """
        Extract document sections from text.
        
        Args:
            text: Extracted text
            
        Returns:
            Dictionary with section names as keys and content as values
        """
        sections = {}
        
        # Common section headers
        section_patterns = [
            r'investment\s*objective[:\s]*(.*?)(?=\n\s*[A-Z][A-Z\s]+:|\n\s*###|\Z)',
            r'exit\s*load[:\s]*(.*?)(?=\n\s*[A-Z][A-Z\s]+:|\n\s*###|\Z)',
            r'tax\s*implications[:\s]*(.*?)(?=\n\s*[A-Z][A-Z\s]+:|\n\s*###|\Z)',
            r'asset\s*allocation[:\s]*(.*?)(?=\n\s*[A-Z][A-Z\s]+:|\n\s*###|\Z)',
            r'about\s*the\s*scheme[:\s]*(.*?)(?=\n\s*[A-Z][A-Z\s]+:|\n\s*###|\Z)',
        ]
        
        section_names = [
            'investment_objective',
            'exit_load',
            'tax_implications',
            'asset_allocation',
            'about_the_scheme'
        ]
        
        for pattern, section_name in zip(section_patterns, section_names):
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                content = match.group(1).strip()
                # Limit content length
                if len(content) > 2000:
                    content = content[:2000] + "..."
                sections[section_name] = content
        
        return sections
    
    def _extract_tables(self, doc) -> List[Dict[str, Any]]:
        """
        Extract tables from PDF document.
        
        Args:
            doc: PyMuPDF document object
            
        Returns:
            List of table dictionaries
        """
        tables = []
        
        for page_num, page in enumerate(doc):
            # Try to find tables using PyMuPDF's find_tables
            try:
                tabs = page.find_tables()
                if tabs.tables:
                    for table in tabs.tables:
                        table_data = {
                            'page': page_num + 1,
                            'rows': len(table.extract()),
                            'cols': len(table.extract()[0]) if table.extract() else 0,
                            'data': table.extract()
                        }
                        tables.append(table_data)
            except Exception as e:
                logger.debug(f"Could not extract tables from page {page_num + 1}: {str(e)}")
        
        return tables


if __name__ == "__main__":
    # Example usage
    extractor = PDFExtractor(use_ocr_fallback=True)
    
    # Test with a sample PDF (if available)
    test_pdf = "./test.pdf"
    if os.path.exists(test_pdf):
        result = extractor.extract_pdf(test_pdf)
        print(f"Extracted {len(result.text)} characters")
        print(f"Structured data: {result.structured_data}")
        print(f"Sections: {list(result.sections.keys())}")
    else:
        print("No test PDF found")
