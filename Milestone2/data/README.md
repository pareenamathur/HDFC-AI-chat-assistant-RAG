# Data Directory

This directory contains all data for the Mutual Fund FAQ Assistant project, organized by processing stage.

## Directory Structure

```
data/
├── raw/           # Raw, unprocessed data from Phase 1.1 (Fetcher)
├── html/          # Scraped HTML files from Groww URLs
├── documents/     # Downloaded PDF documents (factsheets, KIMs, SIDs)
├── processed/     # Cleaned and extracted data from Phases 1.2-1.3
└── indexed/       # Chunked and embedded data ready for vector search
```

## Folder Descriptions

### raw/
Contains raw data as downloaded from sources before any processing.

### html/
Contains scraped HTML files from the 15 whitelisted Groww URLs.
- Organized by scheme name
- Each file contains the full HTML content

### documents/
Contains downloaded PDF documents (factsheets, KIMs, SIDs) from Groww pages.
- Organized by scheme name
- Each document has a SHA-256 checksum for integrity validation

### processed/
Contains cleaned and normalized data after Phases 1.2 (Extractor) and 1.3 (Cleaner & Normalizer).
- Extracted text content
- Structured data (expense ratios, exit loads, etc.)
- Tagged documents with metadata
- Deduplicated content
- Chunked content from Phase 1.4

### indexed/
Contains chunked and embedded data ready for vector search (Phases 1.4-1.6).
- Text chunks (50-1000 characters)
- Associated metadata
- Vector embeddings
- ChromaDB collection files

## Data Flow

```
Phase 1.1 (Fetcher)
    ↓
data/html/ (raw HTML)
data/documents/ (raw PDFs)
    ↓
Phase 1.2 (Extractor)
    ↓
data/processed/ (extracted content)
    ↓
Phase 1.3 (Cleaner & Normalizer)
    ↓
data/processed/ (cleaned content with metadata)
    ↓
Phase 1.4 (Chunker)
    ↓
data/processed/ (chunked content)
    ↓
Phase 1.5 (Embedder)
    ↓
data/indexed/ (embedded chunks)
    ↓
Phase 1.6 (Indexer)
    ↓
data/indexed/ (ChromaDB collection)
```
