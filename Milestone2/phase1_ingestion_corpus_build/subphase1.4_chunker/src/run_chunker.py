"""
Run the Phase 1.4 Chunker to chunk cleaned data.
"""

import sys
import os
import json
from pathlib import Path

# Add src directory to path
sys.path.insert(0, os.path.dirname(__file__))

from chunker import Chunker
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Run the chunker to process cleaned data."""
    logger.info("Starting Phase 1.4 Chunker...")
    
    # Initialize chunker
    chunker = Chunker(min_chunk_size=50, max_chunk_size=1000, chunk_overlap=100)
    
    # Processed data directory
    processed_dir = r'c:\Users\paree\OneDrive\Desktop\Milestone2\data\processed'
    
    # Load cleaned data from Phase 1.3
    input_file = os.path.join(processed_dir, 'cleaned_data_phase1.3.json')
    
    with open(input_file, 'r', encoding='utf-8') as f:
        cleaned_data = json.load(f)
    
    logger.info(f"Loaded {len(cleaned_data)} documents from Phase 1.3")
    
    all_chunks = []
    
    for doc in cleaned_data:
        logger.info(f"Chunking: {doc['scheme_name']}")
        
        try:
            # Chunk the document
            chunks = chunker.chunk_document(
                text=doc['text'],
                sections={},  # No sections available from HTML extraction
                structured_data=doc['cleaned_metadata'],
                document_metadata=doc['metadata']
            )
            
            # Convert chunks to dict for JSON serialization
            for chunk in chunks:
                all_chunks.append({
                    'chunk_id': chunk.chunk_id,
                    'text': chunk.text,
                    'section': chunk.section,
                    'source_document_id': chunk.source_document_id,
                    'metadata': chunk.metadata,
                    'structured_data': chunk.structured_data,
                    'scheme_name': doc['scheme_name']
                })
            
            logger.info(f"Created {len(chunks)} chunks")
            
        except Exception as e:
            logger.error(f"Error chunking {doc['scheme_name']}: {str(e)}")
    
    # Save chunks to JSON
    output_file = os.path.join(processed_dir, 'chunked_data_phase1.4.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_chunks, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Chunked data saved to: {output_file}")
    logger.info(f"Total chunks created: {len(all_chunks)}")
    logger.info(f"Phase 1.4 Chunker complete!")


if __name__ == "__main__":
    main()
