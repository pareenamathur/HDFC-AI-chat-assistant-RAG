"""
Alternate FastAPI entry (phase3 package). Production uses `backend/app.py`.
Lazy-loads RAG on first request to keep Railway RAM low at boot.
"""

from __future__ import annotations

import asyncio
import gc
import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(BASE, "phase2_retrieval_layer", "src"))
sys.path.insert(0, os.path.join(BASE, "phase3_reasoning_guardrails", "src"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MF_API")


class ChatRequest(BaseModel):
    query: str


class ChatResponse(BaseModel):
    answer: str
    source: Optional[str] = None
    source_link: Optional[str] = None
    last_updated: Optional[str] = None
    status: str = "success"


_orchestrator: Any = None
_scheme_names: List[str] = []
_init_error: Optional[str] = None


def _load_schemes() -> List[str]:
    path = os.path.join(BASE, "data", "processed", "chunked_data_phase1.4.json")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        chunks = json.load(f)
    return sorted({c["scheme_name"] for c in chunks})


def _ensure_orchestrator() -> bool:
    global _orchestrator, _init_error
    if _orchestrator is not None:
        return True
    if _init_error:
        return False
    try:
        from orchestrator import RAGOrchestrator

        persist = os.path.join(BASE, "data", "indexed")
        bm25 = os.getenv("USE_BM25", "").lower() in ("1", "true", "yes")
        rerank = os.getenv("USE_RERANKER", "").lower() in ("1", "true", "yes")
        vk = int(os.getenv("VECTOR_FETCH_K", "10"))
        _orchestrator = RAGOrchestrator(
            persist_directory=persist,
            scheme_names=_scheme_names,
            use_bm25=bm25,
            use_reranker=rerank,
            vector_fetch_k=max(4, min(vk, 24)),
        )
        gc.collect()
        return True
    except Exception as e:
        _init_error = str(e)
        logger.exception("Orchestrator init failed")
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _scheme_names
    _scheme_names = _load_schemes()
    logger.info("Phase3 API startup — %s schemes (RAG deferred)", len(_scheme_names))
    yield
    logger.info("Phase3 API shutdown")


def _cors() -> list:
    raw = os.getenv("CORS_ALLOW_ORIGINS", "*").strip()
    if raw == "*":
        return ["*"]
    return [x.strip() for x in raw.split(",") if x.strip()]


app = FastAPI(title="Mutual Fund FAQ Assistant API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def passthrough(request: Request, call_next):
    return await call_next(request)


@app.get("/")
async def root():
    return {"message": "Mutual Fund FAQ Assistant API", "rag_ready": _orchestrator is not None}


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "ready": _orchestrator is not None,
        "schemes_loaded": len(_scheme_names),
        "error": _init_error,
    }


@app.get("/schemes")
async def get_schemes():
    return {"schemes": _scheme_names}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    if not _ensure_orchestrator():
        raise HTTPException(status_code=503, detail=_init_error or "Service unavailable")

    timeout = float(os.getenv("QUERY_TIMEOUT_SECONDS", "90"))
    try:
        async with asyncio.timeout(timeout):
            raw = await asyncio.to_thread(_orchestrator.answer_query, request.query)
        return ChatResponse(
            answer=raw.get("answer", ""),
            source=raw.get("source"),
            source_link=raw.get("source_link"),
            last_updated=raw.get("last_updated"),
            status=raw.get("status", "success"),
        )
    except TimeoutError:
        return ChatResponse(answer="Request timed out.", status="timeout")
    except Exception as e:
        logger.exception("chat error")
        raise HTTPException(status_code=500, detail=str(e)) from e


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        workers=1,
    )
