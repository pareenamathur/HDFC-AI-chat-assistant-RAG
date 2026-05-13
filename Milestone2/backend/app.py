"""
HDFC Mutual Fund Assistant — FastAPI production API (Railway / Docker).
No Streamlit. Heavy models load lazily on first query only.
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

# Must run before importing chromadb / grpc stacks (protobuf compatibility + thread caps).
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("CHROMA_TELEMETRY", "false")

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# backend/app.py -> Milestone2/
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "phase2_retrieval_layer", "src"))
sys.path.insert(0, os.path.join(BASE, "phase3_reasoning_guardrails", "src"))

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger(__name__)


def _memory_mb() -> Optional[float]:
    try:
        import psutil

        return psutil.Process().memory_info().rss / 1024 / 1024
    except Exception:
        return None


def _truthy_env(name: str, default: bool = False) -> bool:
    v = os.getenv(name, "").strip().lower()
    if not v:
        return default
    return v in ("1", "true", "yes", "on")


def _cors_origins() -> List[str]:
    raw = os.getenv("CORS_ALLOW_ORIGINS", "*").strip()
    if raw == "*":
        return ["*"]
    return [x.strip() for x in raw.split(",") if x.strip()]


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
    ready: bool = False
    schemes_loaded: int = 0
    memory_mb: Optional[float] = None


# --- Lazy singleton RAG (instance + failure reason) ---
rag_orchestrator: Any = None
_schemes: List[str] = []
_rag_ready: bool = False
_rag_init_error: Optional[str] = None


def _load_schemes_only() -> List[str]:
    processed = os.getenv(
        "PROCESSED_DATA_PATH", os.path.join(BASE, "data", "processed")
    )
    chunked_data_path = os.path.join(processed, "chunked_data_phase1.4.json")
    if not os.path.exists(chunked_data_path):
        logger.warning("Chunked data missing at %s — schemes list empty.", chunked_data_path)
        return []
    try:
        with open(chunked_data_path, "r", encoding="utf-8") as f:
            chunks = json.load(f)
        schemes = sorted({c["scheme_name"] for c in chunks})
        logger.info("Loaded %s scheme names (startup)", len(schemes))
        return schemes
    except Exception as e:
        logger.exception("Failed loading schemes: %s", e)
        return []


def ensure_rag_orchestrator() -> bool:
    """Lazy-init MiniLM + Chroma + orchestrator on first query; singleton thereafter."""
    global rag_orchestrator, _rag_ready, _rag_init_error

    if _rag_ready and rag_orchestrator is not None:
        return True
    if _rag_init_error:
        return False

    try:
        before = _memory_mb()
        logger.info("Lazy-loading RAG orchestrator (before ~%.1f MB)", before or -1)

        from orchestrator import RAGOrchestrator

        indexed_data_path = os.getenv(
            "INDEXED_DATA_PATH", os.path.join(BASE, "data", "indexed")
        )
        use_bm25 = _truthy_env("USE_BM25", False)
        use_reranker = _truthy_env("USE_RERANKER", False)
        vk_raw = os.getenv("VECTOR_FETCH_K") or os.getenv("STREAMLIT_VECTOR_FETCH_K") or "10"
        vector_fetch_k = max(4, min(int(vk_raw), 24))

        rag_orchestrator = RAGOrchestrator(
            persist_directory=indexed_data_path,
            scheme_names=_schemes,
            use_bm25=use_bm25,
            use_reranker=use_reranker,
            vector_fetch_k=vector_fetch_k,
        )
        _rag_ready = True
        gc.collect()
        after = _memory_mb()
        logger.info("RAG orchestrator ready (after ~%.1f MB)", after or -1)
        return True
    except Exception as e:
        _rag_init_error = str(e)
        logger.exception("RAG initialization failed: %s", e)
        return False


def _run_query_sync(query: str) -> Dict[str, Any]:
    assert rag_orchestrator is not None
    out = rag_orchestrator.answer_query(query)
    gc.collect()
    return out


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _schemes
    logger.info(
        "HDFC MF API boot — BASE=%s RAM=%.1f MB",
        BASE,
        _memory_mb() or -1,
    )
    _schemes = _load_schemes_only()
    mem = _memory_mb()
    logger.info(
        "Startup complete — schemes=%s RAM=%.1f MB (models deferred)",
        len(_schemes),
        mem or -1,
    )
    yield
    logger.info("HDFC MF API shutdown")


app = FastAPI(
    title="HDFC Mutual Fund API",
    description="Production RAG API",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception:
        logger.exception("Unhandled error for %s", request.url.path)
        raise


@app.get("/", response_model=HealthResponse)
async def root():
    return HealthResponse(
        status="healthy",
        message="HDFC Mutual Fund API",
        ready=_rag_ready,
        schemes_loaded=len(_schemes),
        memory_mb=_memory_mb(),
    )


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Always returns if process is up; `ready` indicates RAG warmed."""
    msg = (
        "RAG loaded and ready"
        if _rag_ready
        else (
            "API online — RAG cold (loads on first query)"
            if not _rag_init_error
            else f"API online — RAG failed: {_rag_init_error}"
        )
    )
    return HealthResponse(
        status="healthy",
        message=msg,
        ready=_rag_ready,
        schemes_loaded=len(_schemes),
        memory_mb=_memory_mb(),
    )


@app.get("/schemes", response_model=SchemesResponse)
async def get_schemes():
    return SchemesResponse(schemes=_schemes)


@app.post("/query", response_model=QueryResponse)
async def query_fund(request: QueryRequest):
    q = (request.query or "").strip()
    if not q:
        return QueryResponse(
            answer="Please enter a question.",
            status="error",
        )

    if not ensure_rag_orchestrator():
        detail = _rag_init_error or "Unable to initialize retrieval engine."
        raise HTTPException(status_code=503, detail=detail)

    timeout_s = float(os.getenv("QUERY_TIMEOUT_SECONDS", "90"))
    try:
        async with asyncio.timeout(timeout_s):
            response = await asyncio.to_thread(_run_query_sync, q)
        return QueryResponse(
            answer=response.get("answer", "") or "No answer returned.",
            source=response.get("source"),
            source_link=response.get("source_link"),
            last_updated=response.get("last_updated"),
            status=response.get("status", "error"),
        )
    except TimeoutError:
        logger.warning("Query timed out after %ss", timeout_s)
        return QueryResponse(
            answer="The request took too long. Try a shorter question or retry.",
            status="timeout",
        )
    except Exception as e:
        logger.exception("Query failed")
        return QueryResponse(
            answer="Something went wrong processing your question. Please try again.",
            status="error",
        )


@app.post("/chat", response_model=QueryResponse)
async def chat_with_history(request: QueryRequest):
    """Same as /query; history reserved for future use."""
    return await query_fund(request)


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(
        "backend.app:app",
        host=host,
        port=port,
        workers=1,
        reload=False,
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )
