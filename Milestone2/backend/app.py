"""
Streamlit Backend API for HDFC Mutual Fund Assistant
Provides REST API endpoints for RAG system
"""

import os
import sys
import json
import logging
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add Phase 2 and Phase 3 src to path (lazy import)
# Fix: Correct BASE path calculation - backend is inside Milestone2
# backend/app.py -> backend -> Milestone2
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, 'phase2_retrieval_layer', 'src'))
sys.path.insert(0, os.path.join(BASE, 'phase3_reasoning_guardrails', 'src'))

# Lazy import orchestrator to reduce startup memory
orchestrator = None

def get_orchestrator():
    """Get orchestrator instance (lazy import)."""
    global orchestrator
    if orchestrator is None:
        logger.info("Lazy importing RAGOrchestrator...")
        from orchestrator import RAGOrchestrator
        orchestrator = RAGOrchestrator
        logger.info("RAGOrchestrator imported successfully")
    return orchestrator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="HDFC Mutual Fund API",
    description="Backend API for HDFC Mutual Fund Assistant",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your Vercel domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables for cached components
orchestrator = None
schemes = []

# Pydantic models for request/response
class QueryRequest(BaseModel):
    query: str
    chat_history: List[Dict[str, str]] = []

class QueryResponse(BaseModel):
    answer: str
    source: Optional[str] = None
    source_link: Optional[str] = None
    last_updated: Optional[str] = None
    status: str

class SchemesResponse(BaseModel):
    schemes: List[str]

class HealthResponse(BaseModel):
    status: str
    message: str

# Global variables for lazy loading
orchestrator = None
schemes = []
_orchestrator_initialized = False

def lazy_initialize_orchestrator():
    """Lazy-load ChromaDB and embeddings only when first query happens."""
    global orchestrator, _orchestrator_initialized, schemes
    
    if _orchestrator_initialized:
        logger.info("Orchestrator already initialized, skipping...")
        return True
    
    logger.info("Starting lazy initialization of orchestrator...")
    logger.info("Heavy imports status: LOADING (importing RAG components)")
    
    # Log memory before heavy loading
    before_heavy_memory = get_memory_usage()
    logger.info(f"Memory before heavy loading: {before_heavy_memory} MB")
    
    try:
        # Use environment variables for paths with deployment-safe defaults
        data_path = os.getenv('DATA_PATH', os.path.join(BASE, 'data'))
        processed_data_path = os.getenv('PROCESSED_DATA_PATH', os.path.join(BASE, 'data', 'processed'))
        indexed_data_path = os.getenv('INDEXED_DATA_PATH', os.path.join(BASE, 'data', 'indexed'))
        
        # Load schemes from chunked data
        chunked_data_path = os.path.join(processed_data_path, 'chunked_data_phase1.4.json')
        if os.path.exists(chunked_data_path):
            with open(chunked_data_path, 'r', encoding='utf-8') as f:
                chunks = json.load(f)
            schemes = sorted(list(set(c['scheme_name'] for c in chunks)))
            logger.info(f"Loaded {len(schemes)} schemes")
        else:
            logger.warning(f"Chunked data file not found at: {chunked_data_path}")
            schemes = []
        
        # Initialize orchestrator with maximum memory optimization for Render free tier
        persist_dir = indexed_data_path
        
        # Force disable memory-intensive features for Render free tier
        use_bm25 = False  # Always disabled for free tier
        use_reranker = False  # Always disabled for free tier
        
        logger.info(f"Initializing orchestrator with BM25: {use_bm25}, Reranker: {use_reranker}")
        logger.info(f"Using persist directory: {persist_dir}")
        logger.info("Using memory-optimized configuration for Render free tier")
        
        # Log ChromaDB initialization start
        logger.info("ChromaDB initialization status: STARTING")
        
        # Initialize with minimal memory footprint
        RAGOrchestrator_class = get_orchestrator()
        orchestrator = RAGOrchestrator_class(
            persist_directory=persist_dir,
            scheme_names=schemes,
            use_bm25=use_bm25,
            use_reranker=use_reranker,
            vector_fetch_k=int(os.getenv("STREAMLIT_VECTOR_FETCH_K", "12")),
        )
        
        # Log ChromaDB initialization complete
        logger.info("ChromaDB initialization status: COMPLETED")
        
        # Log embedding model loading
        logger.info("Embedding model status: LOADED (default lightweight model)")
        logger.info("Model loading status: COMPLETED (RAG system ready)")
        
        # Log memory after heavy loading
        after_heavy_memory = get_memory_usage()
        logger.info(f"Memory after heavy loading: {after_heavy_memory} MB")
        
        _orchestrator_initialized = True
        logger.info("Backend initialized successfully (lazy-loaded)")
        return True
    except Exception as e:
        logger.error(f"Error initializing backend: {str(e)}")
        return False

def get_memory_usage():
    """Get current memory usage in MB."""
    try:
        import psutil
        process = psutil.Process()
        memory_info = process.memory_info()
        return memory_info.rss / 1024 / 1024  # Convert to MB
    except ImportError:
        return "Unknown (psutil not available)"

def initialize_backend():
    """Initialize backend components with minimal startup memory usage for Railway."""
    global schemes
    
    # Log startup memory usage
    startup_memory = get_memory_usage()
    logger.info(f"Backend startup: Current RAM usage: {startup_memory} MB")
    logger.info("Backend startup: Loading schemes only (lazy-loading orchestrator)")
    
    try:
        # Use environment variables for paths with deployment-safe defaults
        data_path = os.getenv('DATA_PATH', os.path.join(BASE, 'data'))
        processed_data_path = os.getenv('PROCESSED_DATA_PATH', os.path.join(BASE, 'data', 'processed'))
        
        # Load schemes from chunked data (minimal memory usage)
        chunked_data_path = os.path.join(processed_data_path, 'chunked_data_phase1.4.json')
        if os.path.exists(chunked_data_path):
            with open(chunked_data_path, 'r', encoding='utf-8') as f:
                chunks = json.load(f)
            schemes = sorted(list(set(c['scheme_name'] for c in chunks)))
            logger.info(f"Loaded {len(schemes)} schemes")
        else:
            logger.warning(f"Chunked data file not found at: {chunked_data_path}")
            schemes = []
        
        # Log model loading status (all models deferred)
        logger.info("Model loading status: DEFERRED (will load on first query)")
        logger.info("ChromaDB initialization status: DEFERRED (will initialize on first query)")
        logger.info("Embedding model status: DEFERRED (will load on first query)")
        logger.info("Heavy imports status: DEFERRED (will import on first query)")
        logger.info("sentence-transformers: DEFERRED (will load on first query)")
        logger.info("transformers: DEFERRED (will load on first query)")
        
        # Log memory after schemes loading
        after_schemes_memory = get_memory_usage()
        logger.info(f"Memory after loading schemes: {after_schemes_memory} MB")
        
        # Ensure startup memory is under 300MB for Railway free tier
        if isinstance(after_schemes_memory, (int, float)):
            if after_schemes_memory > 300:
                logger.warning(f"Startup memory {after_schemes_memory}MB exceeds Railway free tier limit of 300MB")
            else:
                logger.info(f"Startup memory {after_schemes_memory}MB is within Railway free tier limit")
        
        # Do NOT initialize orchestrator at startup - lazy load on first query
        logger.info("Orchestrator will be lazy-loaded on first query to minimize startup RAM")
        logger.info("Backend startup complete (minimal memory usage)")
        return True
    except Exception as e:
        logger.error(f"Error initializing backend: {str(e)}")
        return False

@app.on_event("startup")
async def startup_event():
    """Initialize backend on startup."""
    success = initialize_backend()
    if not success:
        logger.error("Failed to initialize backend")

@app.get("/", response_model=HealthResponse)
async def root():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy" if orchestrator else "unhealthy",
        message="HDFC Mutual Fund API is running"
    )

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Detailed health check endpoint."""
    return HealthResponse(
        status="healthy" if orchestrator else "unhealthy",
        message=f"Backend initialized: {orchestrator is not None}, Schemes loaded: {len(schemes)}"
    )

@app.get("/schemes", response_model=SchemesResponse)
async def get_schemes():
    """Get list of available mutual fund schemes."""
    if not schemes:
        raise HTTPException(status_code=503, detail="Schemes not loaded")
    
    return SchemesResponse(schemes=schemes)

@app.post("/query", response_model=QueryResponse)
async def query_fund(request: QueryRequest):
    """Query RAG system for mutual fund information."""
    # Lazy-load orchestrator on first query to minimize startup RAM
    if not lazy_initialize_orchestrator():
        raise HTTPException(status_code=503, detail="Failed to initialize backend")
    
    try:
        logger.info(f"Processing query: {request.query[:100]}...")
        # Process query through orchestrator
        response = orchestrator.answer_query(request.query)
        
        return QueryResponse(
            answer=response.get('answer', 'Sorry, I could not process your query.'),
            source=response.get('source'),
            source_link=response.get('source_link'),
            last_updated=response.get('last_updated'),
            status=response.get('status', 'error')
        )
    except Exception as e:
        logger.error(f"Error processing query: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")

@app.post("/chat", response_model=QueryResponse)
async def chat_with_history(request: QueryRequest):
    """Chat with conversation history support."""
    # Lazy-load orchestrator on first query to minimize startup RAM
    if not lazy_initialize_orchestrator():
        raise HTTPException(status_code=503, detail="Failed to initialize backend")
    
    try:
        logger.info(f"Processing chat query: {request.query[:100]}...")
        # For now, just process current query
        # TODO: Implement conversation history processing
        response = orchestrator.answer_query(request.query)
        
        return QueryResponse(
            answer=response.get('answer', 'Sorry, I could not process your query.'),
            source=response.get('source'),
            source_link=response.get('source_link'),
            last_updated=response.get('last_updated'),
            status=response.get('status', 'error')
        )
    except Exception as e:
        logger.error(f"Error in chat: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error in chat: {str(e)}")

if __name__ == "__main__":
    # Opt-in uvicorn — Streamlit (`streamlit_app.py`) is the deployment entrypoint.
    # If Cloud wrongly Main-files this script, show UI instead of sys.exit (404 health checks).
    from streamlit_misentry import run_backend_cli_or_streamlit_stub

    run_backend_cli_or_streamlit_stub("app:app", logger=logger)
