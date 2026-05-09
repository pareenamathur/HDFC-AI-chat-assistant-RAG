# Phase 0.4 — Technical Stack Selection

## Core Components

### Embeddings
**Selected**: OpenAI `text-embedding-3-small`

**Rationale**:
- Cost-efficient for large corpus
- High-dimensional vectors for better semantic search
- Reliable API with good performance
- Well-documented and widely adopted

**Alternatives Considered**:
- `text-embedding-3-large` (higher cost)
- Open-source models (lower performance, higher operational overhead)

### Vector Store
**Selected**: ChromaDB (local persistence)

**Rationale**:
- Local deployment (no external dependencies)
- Built-in persistence
- Good performance for the expected corpus size
- Easy integration with Python ecosystem
- Metadata filtering support

**Alternatives Considered**:
- Pinecone (cloud-based, adds cost)
- Weaviate (more complex setup)
- FAISS (no built-in persistence, more manual work)

### LLM
**Selected**: Groq (Llama-3)

**Rationale**:
- Extreme speed and low latency
- Strong reasoning capabilities for constraint enforcement
- Cost-effective for high-volume queries
- Easy integration with Groq SDK

**Alternatives Considered**:
- GPT-4o or Claude (higher cost, slightly slower)
- GPT-3.5 Turbo (lower quality)

### Backend
**Selected**: FastAPI

**Rationale**:
- Fast performance with async support
- Automatic API documentation (Swagger UI)
- Type hints and data validation (Pydantic)
- Easy to test and deploy
- Good Python ecosystem integration

**Alternatives Considered**:
- Flask (simpler, but less features)
- Django (overkill for this use case)

### Frontend
**Selected**: React + Vite

**Rationale**:
- Modern, component-based architecture
- Fast development with Vite
- Good ecosystem of UI libraries
- Easy to deploy as static files
- Responsive design capabilities

**Alternatives Considered**:
- Next.js (more complex than needed)
- Vanilla HTML/JS (harder to maintain)

## Supporting Tools

### PDF Extraction
- **PyMuPDF (fitz)**: Primary PDF text extraction
- **Tesseract**: OCR fallback for scanned PDFs
- **Camelot/Unstructured**: Table extraction for complex financial tables

### Web Scraping
- **requests**: HTTP client for fetching URLs
- **BeautifulSoup**: HTML parsing
- **Playwright/Selenium**: Headless browser fallback for JS-rendered content

### Data Processing
- **pandas**: Data manipulation and cleaning
- **numpy**: Numerical operations

### Evaluation
- **RAGAS**: RAG evaluation metrics (faithfulness, relevance)
- **Cohere Rerank**: Reranking for improved retrieval

### Observability
- **Python logging**: Basic logging infrastructure
- **Custom metrics dashboard**: Monitoring and alerting

## Deployment Architecture

```
┌─────────────────┐
│   Frontend      │ (React + Vite, static files)
│   (User Interface)│
└────────┬────────┘
         │ HTTP/JSON
         ↓
┌─────────────────┐
│   Backend API   │ (FastAPI)
│   + PII Filter  │
│   + Logging     │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│  Orchestrator   │ (Intent classification,
│  + Guardrails   │  LLM calls, validation)
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│ Retrieval Layer │ (Vector search,
│ + Reranking     │  metadata filtering)
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│   ChromaDB      │ (Local vector store)
└─────────────────┘
```

## Version Requirements

Pin specific versions in `requirements.txt`:
- `openai>=1.0.0`
- `chromadb>=0.4.0`
- `fastapi>=0.104.0`
- `uvicorn>=0.24.0`
- `pymupdf>=1.23.0`
- `beautifulsoup4>=4.12.0`
- `requests>=2.31.0`
- `ragas>=0.1.0`
- Additional dependencies to be added during implementation
