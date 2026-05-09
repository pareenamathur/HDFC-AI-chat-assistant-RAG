# Fetcher API Reference

## Link Validator

### Class: `LinkValidator`

#### `__init__(timeout: int = 10, user_agent: str = None)`
Initialize the link validator.

**Parameters**:
- `timeout`: Request timeout in seconds (default: 10)
- `user_agent`: Custom User-Agent string (optional)

**Returns**: LinkValidator instance

---

#### `validate_url(url: str) -> ValidationResult`
Validate a single URL.

**Parameters**:
- `url`: URL to validate

**Returns**: ValidationResult object with validation details

**Attributes**:
- `url`: The validated URL
- `is_valid`: Boolean indicating if URL is valid
- `status_code`: HTTP status code (or None)
- `error`: Error message (or None)
- `response_time_ms`: Response time in milliseconds

---

#### `validate_urls(urls: List[str]) -> List[ValidationResult]`
Validate multiple URLs.

**Parameters**:
- `urls`: List of URLs to validate

**Returns**: List of ValidationResult objects

---

#### `get_valid_urls(urls: List[str]) -> Tuple[List[str], List[ValidationResult]]`
Get only valid URLs from a list.

**Parameters**:
- `urls`: List of URLs to validate

**Returns**: Tuple of (valid_urls, all_results)

---

#### `generate_report(results: List[ValidationResult]) -> str`
Generate a validation report.

**Parameters**:
- `results`: List of ValidationResult objects

**Returns**: Formatted report string

---

## Web Scraper

### Class: `WebScraper`

#### `__init__(user_agent: str = None, request_delay: float = 2.0, timeout: int = 30)`
Initialize the web scraper.

**Parameters**:
- `user_agent`: Custom User-Agent string (optional)
- `request_delay`: Delay between requests in seconds (default: 2.0)
- `timeout`: Request timeout in seconds (default: 30)

**Returns**: WebScraper instance

---

#### `scrape_url(url: str) -> ScrapedContent`
Scrape a single URL.

**Parameters**:
- `url`: URL to scrape

**Returns**: ScrapedContent object with scraped data

**Attributes**:
- `url`: The scraped URL
- `html`: HTML content
- `status_code`: HTTP status code
- `title`: Page title
- `scheme_name`: Extracted scheme name
- `links`: List of extracted links
- `error`: Error message (or None)

---

#### `scrape_urls(urls: List[str]) -> List[ScrapedContent]`
Scrape multiple URLs with throttling.

**Parameters**:
- `urls`: List of URLs to scrape

**Returns**: List of ScrapedContent objects

---

#### `save_html(content: ScrapedContent, output_dir: str) -> str`
Save scraped HTML to file.

**Parameters**:
- `content`: ScrapedContent object
- `output_dir`: Directory to save HTML files

**Returns**: Path to saved file (or None if error)

---

## Document Downloader

### Class: `DocumentDownloader`

#### `__init__(output_dir: str = "./downloads", timeout: int = 60, user_agent: str = None)`
Initialize the document downloader.

**Parameters**:
- `output_dir`: Directory to save downloaded documents
- `timeout`: Download timeout in seconds (default: 60)
- `user_agent`: Custom User-Agent string (optional)

**Returns**: DocumentDownloader instance

---

#### `download_document(url: str, filename: str = None) -> DownloadedDocument`
Download a single document.

**Parameters**:
- `url`: URL of the document
- `filename`: Optional custom filename

**Returns**: DownloadedDocument object

**Attributes**:
- `url`: The document URL
- `filepath`: Path to saved file
- `file_type`: Document type (factsheet, kim, sid, other)
- `checksum`: SHA-256 checksum
- `size_bytes`: File size in bytes
- `error`: Error message (or None)

---

#### `extract_and_download_documents(html_content: str, base_url: str, scheme_name: str) -> List[DownloadedDocument]`
Extract document links from HTML and download them.

**Parameters**:
- `html_content`: HTML content of the page
- `base_url`: Base URL of the page
- `scheme_name`: Name of the scheme for folder organization

**Returns**: List of DownloadedDocument objects

---

#### `validate_checksum(filepath: str, expected_checksum: str) -> bool`
Validate file checksum.

**Parameters**:
- `filepath`: Path to the file
- `expected_checksum`: Expected checksum

**Returns**: True if checksum matches, False otherwise

---

## Configuration Manager

### Class: `ConfigManager`

#### `__init__(config_dir: str = None)`
Initialize the configuration manager.

**Parameters**:
- `config_dir`: Directory containing configuration files (optional)

**Returns**: ConfigManager instance

---

#### `load_config() -> FetcherConfig`
Load configuration from YAML files.

**Returns**: FetcherConfig object with all settings

**FetcherConfig Attributes**:
- `urls`: List of whitelisted URLs
- `request_delay`: Delay between requests
- `timeout`: Request timeout
- `user_agent`: User-Agent string
- `output_dir`: Output directory for HTML
- `download_dir`: Output directory for documents
- `enable_checksum_validation`: Checksum validation flag

---

#### `validate_config(config: FetcherConfig) -> bool`
Validate configuration.

**Parameters**:
- `config`: FetcherConfig object

**Returns**: True if valid, False otherwise

---

#### `save_urls(urls: List[Dict[str, str]]) -> None`
Save URLs to configuration file.

**Parameters**:
- `urls`: List of URL dictionaries with 'url' and 'name' keys

---

#### `save_settings(settings: Dict[str, Any]) -> None`
Save settings to configuration file.

**Parameters**:
- `settings`: Dictionary of settings

---

## Convenience Function

### `get_config(config_dir: str = None) -> FetcherConfig`
Convenience function to load and validate configuration.

**Parameters**:
- `config_dir`: Directory containing configuration files (optional)

**Returns**: FetcherConfig object

**Raises**: ValueError if configuration is invalid
