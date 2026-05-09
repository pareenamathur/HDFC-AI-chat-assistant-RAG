"""
Metadata Tagger Module
Assigns unique IDs and tags documents with metadata.
"""

import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging
from dataclasses import dataclass
import hashlib

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class TaggedDocument:
    """Data class to hold tagged document."""
    document_id: str
    scheme_name: str
    document_type: str
    source_url: str
    last_updated_date: str
    category: str
    metadata: Dict[str, Any]
    content_hash: str
    error: str = None


class MetadataTagger:
    """Assigns unique IDs and tags documents with metadata."""
    
    def __init__(self):
        """Initialize the metadata tagger."""
        self.document_types = {
            'factsheet': 'factsheet',
            'kim': 'key_information_memorandum',
            'sid': 'scheme_information_document',
            'html': 'webpage',
            'pdf': 'document'
        }
    
    def tag_document(
        self,
        scheme_name: str,
        document_type: str,
        source_url: str,
        content: str,
        category: str = None,
        additional_metadata: Dict[str, Any] = None
    ) -> TaggedDocument:
        """
        Tag a document with metadata.
        
        Args:
            scheme_name: Name of the scheme
            document_type: Type of document
            source_url: Source URL
            content: Document content
            category: Category of the scheme
            additional_metadata: Additional metadata to include
            
        Returns:
            TaggedDocument object
        """
        try:
            logger.info(f"Tagging document: {scheme_name}")
            
            # Generate unique document ID
            document_id = self._generate_document_id(scheme_name, document_type, source_url)
            
            # Generate content hash
            content_hash = self._generate_content_hash(content)
            
            # Normalize document type
            normalized_doc_type = self._normalize_document_type(document_type)
            
            # Get current date
            last_updated_date = datetime.now().strftime('%Y-%m-%d')
            
            # Build metadata
            metadata = {
                'document_id': document_id,
                'scheme_name': scheme_name,
                'document_type': normalized_doc_type,
                'source_url': source_url,
                'content_length': len(content),
                'created_at': datetime.now().isoformat(),
            }
            
            # Add category if provided
            if category:
                metadata['category'] = category
            
            # Add additional metadata
            if additional_metadata:
                metadata.update(additional_metadata)
            
            return TaggedDocument(
                document_id=document_id,
                scheme_name=scheme_name,
                document_type=normalized_doc_type,
                source_url=source_url,
                last_updated_date=last_updated_date,
                category=category or 'unknown',
                metadata=metadata,
                content_hash=content_hash
            )
            
        except Exception as e:
            logger.error(f"Error tagging document: {str(e)}")
            return TaggedDocument(
                document_id="",
                scheme_name=scheme_name,
                document_type=document_type,
                source_url=source_url,
                last_updated_date="",
                category=category or 'unknown',
                metadata={},
                content_hash="",
                error=str(e)
            )
    
    def _generate_document_id(self, scheme_name: str, document_type: str, source_url: str) -> str:
        """
        Generate a unique document ID.
        
        Args:
            scheme_name: Name of the scheme
            document_type: Type of document
            source_url: Source URL
            
        Returns:
            Unique document ID
        """
        # Create a hash from the combination
        unique_string = f"{scheme_name}_{document_type}_{source_url}"
        hash_obj = hashlib.md5(unique_string.encode())
        hash_hex = hash_obj.hexdigest()
        
        # Create readable ID prefix
        scheme_short = scheme_name.split()[0].lower()[:8]
        doc_type_short = document_type[:4].lower()
        
        return f"{scheme_short}_{doc_type_short}_{hash_hex[:8]}"
    
    def _generate_content_hash(self, content: str) -> str:
        """
        Generate a hash of the content for deduplication.
        
        Args:
            content: Document content
            
        Returns:
            Content hash
        """
        return hashlib.sha256(content.encode()).hexdigest()
    
    def _normalize_document_type(self, document_type: str) -> str:
        """
        Normalize document type to standard format.
        
        Args:
            document_type: Original document type
            
        Returns:
            Normalized document type
        """
        lower_type = document_type.lower()
        
        for key, value in self.document_types.items():
            if key in lower_type:
                return value
        
        return lower_type.replace(' ', '_')
    
    def deduplicate_documents(self, documents: List[TaggedDocument]) -> List[TaggedDocument]:
        """
        Deduplicate documents based on content hash.
        
        Args:
            documents: List of tagged documents
            
        Returns:
            List of unique documents
        """
        seen_hashes = set()
        unique_documents = []
        
        for doc in documents:
            if doc.content_hash not in seen_hashes:
                seen_hashes.add(doc.content_hash)
                unique_documents.append(doc)
            else:
                logger.info(f"Duplicate document removed: {doc.document_id}")
        
        logger.info(f"Deduplicated {len(documents)} -> {len(unique_documents)} documents")
        return unique_documents
    
    def tag_batch(
        self,
        documents: List[Dict[str, Any]]
    ) -> List[TaggedDocument]:
        """
        Tag a batch of documents.
        
        Args:
            documents: List of document dictionaries
            
        Returns:
            List of tagged documents
        """
        tagged_documents = []
        
        for doc in documents:
            tagged = self.tag_document(
                scheme_name=doc.get('scheme_name', ''),
                document_type=doc.get('document_type', 'unknown'),
                source_url=doc.get('source_url', ''),
                content=doc.get('content', ''),
                category=doc.get('category'),
                additional_metadata=doc.get('metadata', {})
            )
            tagged_documents.append(tagged)
        
        return tagged_documents


if __name__ == "__main__":
    # Example usage
    tagger = MetadataTagger()
    
    tagged = tagger.tag_document(
        scheme_name="HDFC Nifty50 Fund",
        document_type="factsheet",
        source_url="https://example.com/factsheet.pdf",
        content="This is the content of the factsheet",
        category="Index Fund"
    )
    
    print(f"Document ID: {tagged.document_id}")
    print(f"Content Hash: {tagged.content_hash}")
    print(f"Metadata: {tagged.metadata}")
