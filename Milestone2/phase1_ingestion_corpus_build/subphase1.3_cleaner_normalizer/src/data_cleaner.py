"""
Data Cleaner Module
Cleans and normalizes extracted text and data.
"""

import re
from typing import Dict, List, Optional, Any
import logging
from dataclasses import dataclass
import uuid

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class CleanedContent:
    """Data class to hold cleaned content."""
    original_text: str
    cleaned_text: str
    removed_boilerplate: List[str]
    normalized_terms: Dict[str, str]
    metadata: Dict[str, Any]
    error: str = None


class DataCleaner:
    """Cleans and normalizes extracted text and data."""
    
    def __init__(self):
        """Initialize the data cleaner."""
        # Financial term normalization mapping
        # Keys are lowercased; only whole-word matches are replaced (word-boundary aware)
        self.term_mapping = {
            'expense ratio': 'expense_ratio',
            'total expense ratio': 'expense_ratio',
            'exit load': 'exit_load',
            'sip amount': 'sip_amount',
            'minimum sip': 'sip_amount',
            'net asset value': 'nav',
        }
        # Order: longer phrases first so "total expense ratio" is tried before "expense ratio"
        self.term_mapping = dict(
            sorted(self.term_mapping.items(), key=lambda x: len(x[0]), reverse=True)
        )
        
        # Boilerplate patterns to remove
        self.boilerplate_patterns = [
            r'\*All investments in mutual funds are subject to market risks.*',
            r'Read all scheme related documents carefully.*',
            r'For more details.*',
            r'Disclaimer.*',
            r'©.*\d{4}.*All rights reserved',
        ]
    
    def clean_text(self, text: str) -> CleanedContent:
        """
        Clean and normalize text.
        
        Args:
            text: Original text
            
        Returns:
            CleanedContent object
        """
        try:
            logger.info("Cleaning text...")
            
            cleaned_text = text
            removed_boilerplate = []
            normalized_terms = {}
            
            # Remove boilerplate
            for pattern in self.boilerplate_patterns:
                matches = re.findall(pattern, cleaned_text, re.IGNORECASE)
                if matches:
                    removed_boilerplate.extend(matches)
                    cleaned_text = re.sub(pattern, '', cleaned_text, flags=re.IGNORECASE)
            
            # Normalize financial terms (whole-word only, case-insensitive)
            for original, normalized in self.term_mapping.items():
                # Use word-boundary pattern so "expense ratio" matches but "long-term" is untouched
                pattern = re.compile(r'\b' + re.escape(original) + r'\b', re.IGNORECASE)
                if pattern.search(cleaned_text):
                    normalized_terms[original] = normalized
                    cleaned_text = pattern.sub(normalized, cleaned_text)
            
            # Remove extra whitespace
            cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
            
            # Remove special characters (keep basic punctuation)
            cleaned_text = re.sub(r'[^\w\s\.\,\-\:\(\)]+', '', cleaned_text)
            
            logger.info(f"Cleaned text: {len(text)} -> {len(cleaned_text)} characters")
            
            return CleanedContent(
                original_text=text,
                cleaned_text=cleaned_text,
                removed_boilerplate=removed_boilerplate,
                normalized_terms=normalized_terms,
                metadata={}
            )
            
        except Exception as e:
            logger.error(f"Error cleaning text: {str(e)}")
            return CleanedContent(
                original_text=text,
                cleaned_text=text,
                removed_boilerplate=[],
                normalized_terms={},
                metadata={},
                error=str(e)
            )
    
    def clean_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Clean and normalize metadata.
        
        Args:
            metadata: Original metadata
            
        Returns:
            Cleaned metadata
        """
        cleaned = {}
        
        for key, value in metadata.items():
            if value:
                # Normalize key names
                normalized_key = key.lower().replace(' ', '_')
                cleaned[normalized_key] = value
        
        return cleaned
    
    def remove_headers_footers(self, text: str) -> str:
        """
        Remove common headers and footers from text.
        
        Args:
            text: Input text
            
        Returns:
            Text with headers/footers removed
        """
        lines = text.split('\n')
        filtered_lines = []
        
        # Patterns that indicate headers/footers
        header_footer_patterns = [
            r'^Page \d+ of \d+$',
            r'^\d+/\d+/\d{4}$',
            r'^Confidential',
            r'^For Internal Use Only',
            r'^www\.',
        ]
        
        for line in lines:
            is_header_footer = False
            for pattern in header_footer_patterns:
                if re.match(pattern, line.strip(), re.IGNORECASE):
                    is_header_footer = True
                    break
            
            if not is_header_footer:
                filtered_lines.append(line)
        
        return '\n'.join(filtered_lines)
    
    def normalize_dates(self, text: str) -> str:
        """
        Normalize date formats in text.
        
        Args:
            text: Input text
            
        Returns:
            Text with normalized dates
        """
        # Convert various date formats to ISO format
        # DD/MM/YYYY -> YYYY-MM-DD
        text = re.sub(r'(\d{2})/(\d{2})/(\d{4})', r'\3-\2-\1', text)
        
        # DD-MM-YYYY -> YYYY-MM-DD
        text = re.sub(r'(\d{2})-(\d{2})-(\d{4})', r'\3-\2-\1', text)
        
        return text


if __name__ == "__main__":
    # Example usage
    cleaner = DataCleaner()
    
    text = """
    HDFC Nifty50 Fund
    Expense Ratio: 0.5%
    TER: 0.5%
    *All investments are subject to market risks*
    """
    
    result = cleaner.clean_text(text)
    print(f"Cleaned text: {result.cleaned_text}")
    print(f"Normalized terms: {result.normalized_terms}")
