# Sub-phase 1.2 — Extractor

**Purpose**: Extract text and structured data from PDFs and HTML documents with OCR fallback for scanned documents.

## Overview

The Extractor is the second component of the Ingestion & Corpus Build pipeline. It extracts text, structured data, and sections from downloaded documents.

## Components

### 1. PDF Extractor (`src/pdf_extractor.py`)
Extracts content from PDF documents with OCR fallback.

**Key Features**:
- PyMuPDF (fitz) for high-fidelity text extraction
- OCR fallback using Tesseract for scanned PDFs
- Structured data extraction (expense ratio, exit load, SIP, etc.)
- Section identification (Investment Objective, Exit Load, etc.)
- Table extraction from PDFs

**Usage**:
```python
from pdf_extractor import PDFExtractor

extractor = PDFExtractor(use_ocr_fallback=True)
result = extractor.extract_pdf("path/to/document.pdf")
print(result.text)
print(result.structured_data)
```

### 2. HTML Extractor (`src/html_extractor.py`)
Extracts content from HTML files.

**Key Features**:
- BeautifulSoup for HTML parsing
- Scheme name extraction
- Structured data extraction
- Document link identification

**Usage**:
```python
from html_extractor import HTMLExtractor

extractor = HTMLExtractor()
result = extractor.extract_html(html_content, url)
print(result.scheme_name)
print(result.structured_data)
```

## Running Tests

```bash
cd phase1_ingestion_corpus_build/subphase1.2_extractor
pytest tests/ -v
```

## Dependencies

- PyMuPDF >= 1.23.0
- pytesseract >= 0.3.10 (for OCR)
- Pillow >= 10.0.0 (for OCR)
- beautifulsoup4 >= 4.12.0

## Status

✅ **COMPLETED** - All components implemented and tested.

## Next Steps

Proceed to Sub-phase 1.3 — Cleaner & Normalizer
