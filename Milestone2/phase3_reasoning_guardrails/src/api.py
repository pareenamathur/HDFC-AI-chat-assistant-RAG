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
    # Opt-in — deployment uses streamlit_app.py; avoid accidental uvicorn from this file.
    if os.getenv("ALLOW_LOCAL_FASTAPI", "").strip().lower() not in ("1", "true", "yes"):
        print(
            "API server not started by default. Use Streamlit for deployment.\n"
            "From repo root: ALLOW_LOCAL_FASTAPI=1 uvicorn phase3_reasoning_guardrails.src.api:app --host 127.0.0.1 --port 8000",
            file=sys.stderr,
        )
        raise SystemExit(0)
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
