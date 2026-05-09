# Sub-phase 1.4 — Chunker

**Purpose**: Chunk text into smaller pieces for vector embedding using section-based and recursive strategies.

## Overview

The Chunker is the fourth component of the Ingestion & Corpus Build pipeline. It splits documents into chunks suitable for vector embedding and retrieval.

## Components

### 1. Chunker (`src/chunker.py`)
Chunks text using section-based and recursive strategies.

**Key Features**:
- **Section-Based Chunking**: Uses sections identified in Phase 1.2 as primary chunk boundaries
- **Structured Data Preservation**: Attaches extracted structured data as metadata to chunks
- **Recursive Character Splitting**: Fallback for sections longer than 1000 characters with 100-character overlap
- **Metadata Attachment**: Each chunk inherits document metadata from Phase 1.3
- **Chunk Validation**: Enforces minimum (50) and maximum (1000) character limits

**Usage**:
```python
from chunker import Chunker

chunker = Chunker(min_chunk_size=50, max_chunk_size=1000, chunk_overlap=100)

chunks = chunker.chunk_document(
    text=document_text,
    sections=extracted_sections,
    structured_data=extracted_data,
    document_metadata=document_metadata
)

for chunk in chunks:
    print(f"{chunk.chunk_id}: {len(chunk.text)} chars - {chunk.section}")
```

## Chunking Strategy

1. **Section-Based**: If sections are available from Phase 1.2, chunk by section boundaries
2. **Recursive Splitting**: For sections longer than 1000 characters, recursively split at natural break points
3. **Fallback**: If no sections available, use recursive character splitting on full text
4. **Metadata**: Each chunk inherits document metadata and structured data

## Running Tests

```bash
cd phase1_ingestion_corpus_build/subphase1.4_chunker
pytest tests/ -v
```

## Status

✅ **COMPLETED** - All components implemented and tested.

## Next Steps

Proceed to Sub-phase 1.5 — Embedder
