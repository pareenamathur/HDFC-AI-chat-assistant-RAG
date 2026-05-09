# Sub-phase 1.3 — Cleaner & Normalizer

**Purpose**: Clean, normalize, and tag extracted data with metadata for consistency.

## Overview

The Cleaner & Normalizer is the third component of the Ingestion & Corpus Build pipeline. It removes boilerplate, normalizes financial terms, and tags documents with metadata.

## Components

### 1. Data Cleaner (`src/data_cleaner.py`)
Cleans and normalizes extracted text.

**Key Features**:
- Boilerplate removal (disclaimers, footers, headers)
- Financial term normalization (Expense Ratio → expense_ratio)
- Date normalization
- Metadata cleaning
- Header/footer removal

**Usage**:
```python
from data_cleaner import DataCleaner

cleaner = DataCleaner()
result = cleaner.clean_text(text)
print(result.cleaned_text)
print(result.normalized_terms)
```

### 2. Metadata Tagger (`src/metadata_tagger.py`)
Assigns unique IDs and tags documents with metadata.

**Key Features**:
- Unique document ID generation
- Content hash generation for deduplication
- Metadata tagging (scheme_name, document_type, source_url, etc.)
- Document deduplication based on content hash

**Usage**:
```python
from metadata_tagger import MetadataTagger

tagger = MetadataTagger()
tagged = tagger.tag_document(
    scheme_name="HDFC Nifty50 Fund",
    document_type="factsheet",
    source_url="https://example.com/factsheet.pdf",
    content="document content",
    category="Index Fund"
)
print(tagged.document_id)
print(tagged.metadata)
```

## Running Tests

```bash
cd phase1_ingestion_corpus_build/subphase1.3_cleaner_normalizer
pytest tests/ -v
```

## Status

✅ **COMPLETED** - All components implemented and tested.

## Next Steps

Proceed to Sub-phase 1.4 — Chunker
