# Sub-phase 1.1 — Fetcher

**Purpose**: Crawl the 15 whitelisted Groww URLs and download linked documents (factsheets, KIMs, SIDs) with checksum validation.

## Overview

The Fetcher is the first component of the Ingestion & Corpus Build pipeline. It validates URLs, scrapes HTML content, and downloads official documents from Groww pages.

## Components

### 1. Link Validator (`src/link_validator.py`)
Validates URL accessibility before processing to avoid wasting resources on dead links.

**Key Features**:
- HTTP status code validation
- Timeout handling
- Response time tracking
- Detailed validation reports

**Usage**:
```python
from link_validator import LinkValidator

validator = LinkValidator(timeout=10)
results = validator.validate_urls(urls)
report = validator.generate_report(results)
```

### 2. Web Scraper (`src/web_scraper.py`)
Crawls whitelisted URLs and extracts HTML content with bot detection avoidance.

**Key Features**:
- Custom User-Agent headers
- Request throttling (configurable delay)
- HTML parsing with BeautifulSoup
- Scheme name extraction
- Link extraction

**Usage**:
```python
from web_scraper import WebScraper

scraper = WebScraper(request_delay=2.0)
results = scraper.scrape_urls(urls)
```

### 3. Document Downloader (`src/document_downloader.py`)
Downloads linked factsheets, KIMs, SIDs from Groww pages with checksum validation.

**Key Features**:
- PDF document download
- SHA-256 checksum validation
- Document type detection (factsheet, KIM, SID)
- Scheme-specific directory organization

**Usage**:
```python
from document_downloader import DocumentDownloader

downloader = DocumentDownloader(output_dir="./downloads")
results = downloader.extract_and_download_documents(html, base_url, scheme_name)
```

### 4. Configuration Manager (`src/config.py`)
Centralized configuration management for the fetcher.

**Key Features**:
- YAML-based configuration
- URL list management
- Settings management
- Configuration validation

**Usage**:
```python
from config import get_config

config = get_config()
print(config.urls)
```

## Configuration

Configuration files are located in the `config/` directory:

### `config/urls.yaml`
Contains the 15 whitelisted Groww URLs with scheme names and categories.

### `config/settings.yaml`
Contains fetcher settings:
- Request delay (throttling)
- Timeout settings
- User agent string
- Output directories
- Checksum validation flag

## Folder Structure

```
subphase1.1_fetcher/
├── src/                    # Python source code
│   ├── link_validator.py
│   ├── web_scraper.py
│   ├── document_downloader.py
│   └── config.py
├── tests/                   # Unit tests
│   ├── test_link_validator.py
│   ├── test_web_scraper.py
│   └── test_document_downloader.py
├── config/                  # Configuration files
│   ├── urls.yaml
│   └── settings.yaml
├── docs/                    # Documentation
│   ├── fetcher_design.md
│   └── api_reference.md
└── README.md
```

## Running Tests

```bash
cd phase1_ingestion_corpus_build/subphase1.1_fetcher
pytest tests/ -v
```

## Running the Fetcher

```bash
cd phase1_ingestion_corpus_build/subphase1.1_fetcher/src
python link_validator.py  # Validate URLs
python web_scraper.py      # Scrape URLs
python document_downloader.py  # Download documents
```

## Dependencies

See project-wide `requirements.txt` in the root directory.

## Status

✅ **COMPLETED** - All components implemented and tested.

## Next Steps

Proceed to Sub-phase 1.2 — Extractor
