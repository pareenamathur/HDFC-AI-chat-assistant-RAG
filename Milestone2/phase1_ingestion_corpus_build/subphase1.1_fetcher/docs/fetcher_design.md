# Fetcher Design Document

## Architecture Overview

The Fetcher is designed as a modular pipeline with three main components:

```
┌─────────────────┐
│  Link Validator │ → Validates URLs before processing
└────────┬────────┘
         │ Valid URLs
         ↓
┌─────────────────┐
│   Web Scraper   │ → Scrapes HTML content
└────────┬────────┘
         │ HTML Content
         ↓
┌─────────────────┐
│ Doc Downloader  │ → Downloads PDF documents
└─────────────────┘
```

## Component Interactions

### 1. Link Validator → Web Scraper
- **Input**: List of URLs from configuration
- **Output**: List of valid URLs
- **Purpose**: Filter out dead/invalid URLs before scraping

### 2. Web Scraper → Document Downloader
- **Input**: Valid URLs
- **Output**: HTML content + scheme names
- **Purpose**: Extract HTML for document link discovery

### 3. Document Downloader → Output
- **Input**: HTML content + base URL + scheme name
- **Output**: Downloaded PDF files with checksums
- **Purpose**: Persist official documents for extraction

## Error Handling Strategy

### Link Validator
- **Timeout**: Return ValidationResult with error message
- **Connection Error**: Return ValidationResult with error message
- **HTTP Errors**: Return ValidationResult with status code
- **Unexpected Errors**: Log and return ValidationResult with error

### Web Scraper
- **Timeout**: Return ScrapedContent with error message
- **Connection Error**: Return ScrapedContent with error message
- **HTTP Errors**: Return ScrapedContent with status code
- **Parse Errors**: Return ScrapedContent with error message

### Document Downloader
- **Timeout**: Return DownloadedDocument with error message
- **Download Errors**: Return DownloadedDocument with error message
- **Checksum Mismatch**: Log error but keep document (configurable)
- **File System Errors**: Log error and return DownloadedDocument with error

## Throttling Strategy

To avoid bot detection from Groww:
1. **Request Delay**: Configurable delay between requests (default: 2 seconds)
2. **User-Agent**: Custom browser-like User-Agent string
3. **Session Management**: Reuse HTTP session for connection pooling
4. **Retry Logic**: Configurable retry with exponential backoff (future enhancement)

## Checksum Validation

All downloaded documents are validated using SHA-256 checksums:
1. Calculate checksum immediately after download
2. Store checksum in metadata
3. Can be used for integrity verification later
4. Configurable via `enable_checksum_validation` setting

## Logging Strategy

- **Level**: INFO by default (configurable)
- **File**: Logs written to `./logs/fetcher.log`
- **Format**: Timestamp + Level + Message
- **Key Events**:
  - URL validation start/completion
  - Scraping start/completion
  - Download start/completion
  - Errors and warnings

## Data Flow

```
1. Load URLs from config/urls.yaml
2. Validate all URLs (link_validator.py)
3. Filter valid URLs
4. Scrape valid URLs (web_scraper.py)
5. Extract HTML and scheme names
6. For each scraped page:
   a. Find document links (factsheet, KIM, SID)
   b. Download documents (document_downloader.py)
   c. Calculate checksums
   d. Save to scheme-specific directory
7. Generate validation report
```

## Configuration Management

Configuration is centralized in `config.py`:
- **URLs**: Loaded from `config/urls.yaml`
- **Settings**: Loaded from `config/settings.yaml`
- **Validation**: ConfigManager validates all settings
- **Defaults**: Fallback to defaults if config missing

## Extensibility

The fetcher is designed for easy extension:
1. **New URL Sources**: Add to `urls.yaml`
2. **New Document Types**: Extend `_determine_file_type()` method
3. **New Scraping Targets**: Extend WebScraper class
4. **Custom Validation**: Extend LinkValidator class

## Performance Considerations

1. **Sequential Processing**: URLs processed sequentially to respect throttling
2. **Streaming Downloads**: Large files downloaded in chunks
3. **Connection Pooling**: HTTP session reused for efficiency
4. **Memory Usage**: HTML content not kept in memory after processing

## Security Considerations

1. **URL Validation**: Only process whitelisted URLs
2. **File Size Limits**: Configurable max file size (future enhancement)
3. **Path Traversal**: Safe filename generation from URLs
4. **Input Sanitization**: All inputs validated before use
