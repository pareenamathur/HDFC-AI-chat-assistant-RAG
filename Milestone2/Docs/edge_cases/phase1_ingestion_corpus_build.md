# Phase 1 — Ingestion & Corpus Build (Offline Pipeline) Edge Cases

*Focus: Data extraction quality, consistency, and pipeline reliability.*

---

## **Sub-phase 1.1 — Fetcher**

### **EC 1.1.1: Rate Limiting**
- **Scenario**: Groww implements stricter rate limits after initial crawl.
- **Mitigation**: Implement exponential backoff and configurable delay between requests.

### **EC 1.1.2: Dynamic Content**
- **Scenario**: Content is loaded via JavaScript and not available in initial HTML.
- **Mitigation**: Use headless browsers (Playwright/Selenium) as fallback for JS-rendered content.

---

## **Sub-phase 1.2 — Extractor**

### **EC 1.2.1: Scanned PDF Documents**
- **Scenario**: Some older factsheets or SIDs are uploaded as images rather than text-searchable PDFs.
- **Mitigation**: Fallback to OCR (Optical Character Recognition) using tools like `Tesseract` or `Azure Form Recognizer`.

### **EC 1.2.2: Complex Table Structures**
- **Scenario**: Expense ratios or exit loads are buried in nested tables that `fitz` extracts as a jumble of text.
- **Mitigation**: Use specialized table extractors like `Camelot` or `Unstructured` to maintain structural integrity.

### **EC 1.2.3: Partial Data Extraction**
- **Scenario**: A document is partially downloaded or corrupted.
- **Mitigation**: Checksum validation for PDFs and minimum character count checks per document.

---

## **Sub-phase 1.3 — Cleaner & Normalizer**

### **EC 1.3.1: Inconsistent Terminology**
- **Scenario**: Same concept referred to as "Expense Ratio", "TER", "Total Expense Ratio" across documents.
- **Mitigation**: Create a canonical term mapping dictionary and normalize during cleaning.

### **EC 1.3.2: Metadata Inconsistency**
- **Scenario**: Different documents have different metadata formats or missing fields.
- **Mitigation**: Implement schema validation with fallback defaults for missing metadata.

---

## **Sub-phase 1.4 — Chunker**

### **EC 1.4.1: Context Loss at Boundaries**
- **Scenario**: Critical information split across chunk boundaries (e.g., "Exit load is 1% if redeemed" in one chunk, "within 30 days" in next).
- **Mitigation**: Use semantic chunking based on headers and increase overlap for financial tables.

### **EC 1.4.2: Variable Chunk Quality**
- **Scenario**: Some chunks contain mostly boilerplate or navigation text.
- **Mitigation**: Implement quality scoring and filter out low-information chunks.

---

## **Sub-phase 1.5 — Embedder**

### **EC 1.5.1: API Rate Limits**
- **Scenario**: OpenAI embedding API rate limits during batch processing.
- **Mitigation**: Implement batching with rate limit handling and retry logic.

### **EC 1.5.2: Embedding Dimension Mismatch**
- **Scenario**: Embedding model updates change output dimensions.
- **Mitigation**: Pin model version and validate dimensions before indexing.

---

## **Sub-phase 1.6 — Indexer**

### **EC 1.6.1: Storage Exhaustion**
- **Scenario**: Vector database grows beyond available disk space.
- **Mitigation**: Monitor storage usage and implement archival/deletion of old corpus versions.

### **EC 1.6.2: Index Corruption**
- **Scenario**: ChromaDB index becomes corrupted during write operation.
- **Mitigation**: Implement transaction-like writes with rollback capability and regular backups.

---

## **Sub-phase 1.7 — Refresh & Health**

### **EC 1.7.1: Stale Data Detection**
- **Scenario**: Source documents update but corpus refresh fails silently.
- **Mitigation**: Implement content hash comparison and alert on refresh failures.

### **EC 1.7.2: Cron Job Failures**
- **Scenario**: Monthly re-indexing cron job fails due to system downtime or API changes.
- **Mitigation**: Implement retry logic with escalation alerts and manual trigger capability.
