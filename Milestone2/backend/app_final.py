"""
Streamlit Backend API for HDFC Mutual Fund Assistant
Provides REST API endpoints for RAG system
"""

import os
import sys
import json
import logging
from typing import Dict, Any, List
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add Phase 2 and Phase 3 src to path
# Fix: Correct BASE path calculation - backend is inside Milestone2
# backend/app.py -> backend -> Milestone2
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, 'phase2_retrieval_layer', 'src'))
sys.path.insert(0, os.path.join(BASE, 'phase3_reasoning_guardrails', 'src'))

from orchestrator import RAGOrchestrator

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
    source: str = None
    source_link: str = None
    last_updated: str = None
    status: str

class SchemesResponse(BaseModel):
    schemes: List[str]

class HealthResponse(BaseModel):
    status: str
    message: str

def initialize_backend():
    """Initialize backend components."""
    global orchestrator, schemes
    
    try:
        # Load schemes from chunked data
        chunked_data_path = os.path.join(BASE, 'data', 'processed', 'chunked_data_phase1.4.json')
        if os.path.exists(chunked_data_path):
            with open(chunked_data_path, 'r', encoding='utf-8') as f:
                chunks = json.load(f)
            schemes = sorted(list(set(c['scheme_name'] for c in chunks)))
            logger.info(f"Loaded {len(schemes)} schemes")
        
        # Initialize orchestrator with memory optimization
        persist_dir = os.path.join(BASE, 'data', 'indexed')
        use_bm25 = os.getenv('USE_BM25', 'false').lower() == 'true'
        use_reranker = os.getenv('USE_RERANKER', 'false').lower() == 'true'
        
        logger.info(f"Initializing orchestrator with BM25: {use_bm25}, Reranker: {use_reranker}")
        
        orchestrator = RAGOrchestrator(
            persist_directory=persist_dir,
            scheme_names=schemes,
            use_bm25=use_bm25,
            use_reranker=use_reranker
        )
        
        logger.info("Backend initialized successfully")
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
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Backend not initialized")
    
    try:
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
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Backend not initialized")
    
    try:
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
    if os.getenv("ALLOW_LOCAL_FASTAPI", "").strip().lower() not in ("1", "true", "yes"):
        print(
            "FastAPI is opt-in. Deployment uses streamlit_app.py.\n"
            "ALLOW_LOCAL_FASTAPI=1 python app_final.py",
            file=sys.stderr,
        )
        raise SystemExit(0)
    import uvicorn

    uvicorn.run(
        "app_final:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8501")),
        reload=False,
        access_log=True,
    )
