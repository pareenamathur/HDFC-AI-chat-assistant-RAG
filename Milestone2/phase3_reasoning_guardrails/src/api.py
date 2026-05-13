import os
import sys
import json
import logging
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from contextlib import asynccontextmanager
from dotenv import load_dotenv

from fastapi.middleware.cors import CORSMiddleware

# Load environment variables from .env file
load_dotenv()

# Add Phase 2 and 3 src to path
BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(BASE, 'phase2_retrieval_layer', 'src'))
sys.path.insert(0, os.path.join(BASE, 'phase3_reasoning_guardrails', 'src'))

from orchestrator import RAGOrchestrator

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MF_API")

class ChatRequest(BaseModel):
    query: str

class ChatResponse(BaseModel):
    answer: str
    source: Optional[str] = None
    status: str

orchestrator = None
scheme_names_list = []

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize orchestrator
    global orchestrator, scheme_names_list
    
    # Load schemes
    chunked_data_path = os.path.join(BASE, 'data', 'processed', 'chunked_data_phase1.4.json')
    if not os.path.exists(chunked_data_path):
        logger.error(f"Data file not found at {chunked_data_path}")
        scheme_names_list = []
    else:
        with open(chunked_data_path, 'r', encoding='utf-8') as f:
            chunks = json.load(f)
        scheme_names_list = sorted(list(set(c['scheme_name'] for c in chunks)))

    persist_dir = os.path.join(BASE, 'data', 'indexed')
    orchestrator = RAGOrchestrator(persist_directory=persist_dir, scheme_names=scheme_names_list)
    logger.info("Orchestrator initialized.")
    yield

app = FastAPI(title="Mutual Fund FAQ Assistant API", lifespan=lifespan)

# Add CORS Middleware for Phase 4 Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this to the frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def pii_filter_middleware(request: Request, call_next):
    # Simple PII filtering placeholder
    return await call_next(request)

@app.get("/")
async def root():
    return {"message": "Mutual Fund FAQ Assistant API is running."}

@app.get("/health")
async def health():
    return {
        "status": "healthy" if orchestrator else "initializing",
        "schemes_loaded": len(scheme_names_list)
    }

@app.get("/schemes")
async def get_schemes():
    return {"schemes": scheme_names_list}

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Service not ready")
    
    try:
        response = orchestrator.answer_query(request.query)
        return response
    except Exception as e:
        logger.exception("Error during chat processing")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    from pathlib import Path

    _backend = Path(__file__).resolve().parents[2] / "backend"
    if str(_backend) not in sys.path:
        sys.path.insert(0, str(_backend))
    from streamlit_misentry import run_backend_cli_or_streamlit_stub

    # Pass ASGI app object (opt-in). If Cloud Main-file points here, show stub page — no sys.exit(0).
    run_backend_cli_or_streamlit_stub(None, uvicorn_app=app, default_port="8000")
