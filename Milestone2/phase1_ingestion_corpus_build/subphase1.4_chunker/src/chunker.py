"""
Chunker Module
Chunks text into smaller pieces for vector embedding with section-based and recursive strategies.
"""

from typing import Dict, List, Optional, Any
import logging
from dataclasses import dataclass
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class Chunk:
    """Data class to hold a text chunk."""
    chunk_id: str
    text: str
    metadata: Dict[str, Any]
    section: str
    source_document_id: str
    structured_data: Dict[str, Any]
    error: str = None


class Chunker:
    """Chunks text into smaller pieces for vector embedding."""
    
    def __init__(
        self,
        min_chunk_size: int = 50,
        max_chunk_size: int = 1000,
        chunk_overlap: int = 100
    ):
        """
        Initialize the chunker.
        
        Args:
            min_chunk_size: Minimum characters per chunk
            max_chunk_size: Maximum characters per chunk
            chunk_overlap: Character overlap between chunks
        """
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.chunk_overlap = chunk_overlap
    
    def chunk_document(
        self,
        text: str,
        sections: Dict[str, str],
        structured_data: Dict[str, Any],
        document_metadata: Dict[str, Any]
    ) -> List[Chunk]:
        """
        Chunk a document using section-based strategy.
        
        Args:
            text: Full document text
            sections: Dictionary of section names to content
            structured_data: Extracted structured data
            document_metadata: Document metadata from Phase 1.3
            
        Returns:
            List of Chunk objects
        """
        try:
            logger.info(f"Chunking document: {document_metadata.get('scheme_name', 'Unknown')}")
            
            chunks = []
            
            # If sections are available, use section-based chunking
            if sections:
                chunks = self._chunk_by_sections(
                    sections,
                    structured_data,
                    document_metadata
                )
            else:
                # Fall back to recursive character splitting
                chunks = self._chunk_by_recursion(
                    text,
                    structured_data,
                    document_metadata
                )
            
            # Validate chunks
            chunks = self._validate_chunks(chunks)
            
            logger.info(f"Created {len(chunks)} chunks")
            
            return chunks
            
        except Exception as e:
            logger.error(f"Error chunking document: {str(e)}")
            return []
    
    def _chunk_by_sections(
        self,
        sections: Dict[str, str],
        structured_data: Dict[str, Any],
        document_metadata: Dict[str, Any]
    ) -> List[Chunk]:
        """
        Chunk by sections identified in Phase 1.2.
        
        Args:
            sections: Dictionary of section names to content
            structured_data: Extracted structured data
            document_metadata: Document metadata
            
        Returns:
            List of Chunk objects
        """
        chunks = []
        chunk_counter = 0
        
        for section_name, section_content in sections.items():
            if not section_content or len(section_content.strip()) < self.min_chunk_size:
                continue
            
            # If section is too long, split it recursively
            if len(section_content) > self.max_chunk_size:
                section_chunks = self._recursive_split(section_content)
                
                for i, chunk_text in enumerate(section_chunks):
                    chunk = self._create_chunk(
                        chunk_text,
                        section_name,
                        structured_data,
                        document_metadata,
                        chunk_counter
                    )
                    chunks.append(chunk)
                    chunk_counter += 1
            else:
                chunk = self._create_chunk(
                    section_content,
                    section_name,
                    structured_data,
                    document_metadata,
                    chunk_counter
                )
                chunks.append(chunk)
                chunk_counter += 1
        
        return chunks
    
    def _chunk_by_recursion(
        self,
        text: str,
        structured_data: Dict[str, Any],
        document_metadata: Dict[str, Any]
    ) -> List[Chunk]:
        """
        Chunk using recursive character splitting.
        
        Args:
            text: Full text to chunk
            structured_data: Extracted structured data
            document_metadata: Document metadata
            
        Returns:
            List of Chunk objects
        """
        chunks = []
        chunk_counter = 0
        
        text_chunks = self._recursive_split(text)
        
        for chunk_text in text_chunks:
            if len(chunk_text) >= self.min_chunk_size:
                chunk = self._create_chunk(
                    chunk_text,
                    "general",
                    structured_data,
                    document_metadata,
                    chunk_counter
                )
                chunks.append(chunk)
                chunk_counter += 1
        
        return chunks
    
    def _recursive_split(self, text: str) -> List[str]:
        """
        Recursively split text into chunks.
        
        Args:
            text: Text to split
            
        Returns:
            List of text chunks
        """
        if len(text) <= self.max_chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = min(start + self.max_chunk_size, len(text))
            
            # Try to split at a natural break point
            if end < len(text):
                # Look for sentence boundary
                for delimiter in ['.', '!', '?', '\n']:
                    last_delimiter = text.rfind(delimiter, start, end)
                    if last_delimiter > start + self.min_chunk_size:
                        end = last_delimiter + 1
                        break
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            next_start = end - self.chunk_overlap
            # Guarantee forward progress to avoid infinite loops
            if next_start <= start:
                next_start = end
            start = next_start
        
        return chunks
    
    def _create_chunk(
        self,
        text: str,
        section: str,
        structured_data: Dict[str, Any],
        document_metadata: Dict[str, Any],
        chunk_counter: int
    ) -> Chunk:
        """
        Create a Chunk object with metadata.
        
        Args:
            text: Chunk text
            section: Section name
            structured_data: Extracted structured data
            document_metadata: Document metadata
            chunk_counter: Chunk number
            
        Returns:
            Chunk object
        """
        document_id = document_metadata.get('document_id', 'unknown')
        chunk_id = f"{document_id}_chunk_{chunk_counter}"
        
        # Attach document metadata to chunk
        chunk_metadata = document_metadata.copy()
        chunk_metadata['section'] = section
        chunk_metadata['chunk_number'] = chunk_counter
        chunk_metadata['chunk_length'] = len(text)
        
        # Attach relevant structured data
        chunk_structured_data = {}
        for key, value in structured_data.items():
            if value:
                chunk_structured_data[key] = value
        
        return Chunk(
            chunk_id=chunk_id,
            text=text,
            metadata=chunk_metadata,
            section=section,
            source_document_id=document_id,
            structured_data=chunk_structured_data
        )
    
    def _validate_chunks(self, chunks: List[Chunk]) -> List[Chunk]:
        """
        Validate chunks and remove invalid ones.
        
        Args:
            chunks: List of chunks to validate
            
        Returns:
            List of valid chunks
        """
        valid_chunks = []
        
        for chunk in chunks:
            # Check minimum size
            if len(chunk.text) < self.min_chunk_size:
                logger.warning(f"Chunk {chunk.chunk_id} too small: {len(chunk.text)} characters")
                continue
            
            # Check maximum size
            if len(chunk.text) > self.max_chunk_size:
                logger.warning(f"Chunk {chunk.chunk_id} too large: {len(chunk.text)} characters")
                # Truncate to max size
                chunk.text = chunk.text[:self.max_chunk_size]
            
            # Check semantic coherence (basic check)
            if not chunk.text.strip():
                logger.warning(f"Chunk {chunk.chunk_id} is empty")
                continue
            
            valid_chunks.append(chunk)
        
        logger.info(f"Validated {len(chunks)} -> {len(valid_chunks)} chunks")
        return valid_chunks
    
    def chunk_batch(
        self,
        documents: List[Dict[str, Any]]
    ) -> List[Chunk]:
        """
        Chunk a batch of documents.
        
        Args:
            documents: List of document dictionaries
            
        Returns:
            List of all chunks from all documents
        """
        all_chunks = []
        
        for doc in documents:
            chunks = self.chunk_document(
                text=doc.get('text', ''),
                sections=doc.get('sections', {}),
                structured_data=doc.get('structured_data', {}),
                document_metadata=doc.get('metadata', {})
            )
            all_chunks.extend(chunks)
        
        return all_chunks


if __name__ == "__main__":
    # Example usage
    chunker = Chunker(min_chunk_size=50, max_chunk_size=1000, chunk_overlap=100)
    
    sections = {
        'investment_objective': 'To provide returns that correspond to the total returns of the Nifty 50 Index.',
        'exit_load': '1% if redeemed within 30 days. Nil after 30 days.'
    }
    
    structured_data = {
        'expense_ratio': '0.5%',
        'exit_load': '1%'
    }
    
    document_metadata = {
        'document_id': 'hdfc_nifty50_factsheet',
        'scheme_name': 'HDFC Nifty50 Fund',
        'document_type': 'factsheet',
        'source_url': 'https://example.com/factsheet.pdf',
        'category': 'Index Fund'
    }
    
    chunks = chunker.chunk_document(
        text="Full document text here...",
        sections=sections,
        structured_data=structured_data,
        document_metadata=document_metadata
    )
    
    print(f"Created {len(chunks)} chunks")
    for chunk in chunks:
        print(f"  {chunk.chunk_id}: {len(chunk.text)} chars - {chunk.section}")
