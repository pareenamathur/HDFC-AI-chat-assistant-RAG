"""
HDFC Mutual Fund Assistant — FastAPI production API (Railway / Docker).
Boots with zero env vars; RAG is lazy; missing index or keys → graceful degradation.
"""

from __future__ import annotations

import asyncio
import gc
import json
import logging
import os
import sys
import threading
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

# Before chromadb / grpc (protobuf + thread caps).
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("CHROMA_TELEMETRY", "false")

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

# backend/app.py -> Milestone2/
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "phase2_retrieval_layer", "src"))
sys.path.insert(0, os.path.join(BASE, "phase3_reasoning_guardrails", "src"))

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Safe defaults — missing env must never crash the process
# ---------------------------------------------------------------------------
def _str_env(name: str, default: str = "") -> str:
    try:
        v = os.getenv(name)
        if v is None:
            return default
        return str(v).strip()
    except Exception:
        return default


def _float_env(name: str, default: float) -> float:
    try:
        raw = os.getenv(name)
        if raw is None or not str(raw).strip():
            return default
        return float(str(raw).strip())
    except (TypeError, ValueError):
        return default


def _int_env(name: str, default: int, lo: int, hi: int) -> int:
    try:
        raw = os.getenv(name)
        if raw is None or not str(raw).strip():
            n = default
        else:
            n = int(str(raw).strip())
        return max(lo, min(n, hi))
    except (TypeError, ValueError):
        return default


def _bool_env(name: str, default: bool = False) -> bool:
    v = _str_env(name, "").lower()
    if not v:
        return default
    return v in ("1", "true", "yes", "on")


def _cors_origins() -> List[str]:
    raw = _str_env("CORS_ALLOW_ORIGINS", "*")
    if not raw or raw == "*":
        return ["*"]
    parts = [x.strip() for x in raw.split(",") if x.strip()]
    return parts if parts else ["*"]


def _has_groq_key() -> bool:
    return bool(_str_env("GROQ_API_KEY", ""))


def _indexed_dir() -> str:
    return _str_env("INDEXED_DATA_PATH", "") or os.path.join(BASE, "data", "indexed")


def _memory_mb() -> Optional[float]:
    try:
        import psutil

        return psutil.Process().memory_info().rss / 1024 / 1024
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Runtime state (lazy RAG + degradation)
# ---------------------------------------------------------------------------
rag_orchestrator: Any = None
_schemes: List[str] = []
# API is "ready" for traffic after lifespan — never false for a running worker.
_api_ready: bool = False
# Full RAG (Chroma + retriever) initialized successfully.
_chroma_loaded: bool = False
# Embedding / sentence-transformers warmed (first successful retriever use).
_model_loaded: bool = False
_rag_init_attempted: bool = False
_rag_init_error: Optional[str] = None
_degraded_no_rag: bool = False
_rag_init_lock = threading.Lock()


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
    """Health payload; handler wraps failures so this model is best-effort."""

    status: str = Field(default="healthy")
    ready: bool = Field(default=True)
    message: str = Field(default="")
    schemes_loaded: int = Field(default=0)
    memory_mb: Optional[float] = None
    model_loaded: bool = Field(default=False)
    chroma_loaded: bool = Field(default=False)
    mock_mode: bool = Field(default=True)
    degraded: bool = Field(default=False)


def _load_schemes_only() -> List[str]:
    processed = _str_env("PROCESSED_DATA_PATH", "") or os.path.join(BASE, "data", "processed")
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


def _fallback_query_response(query: str) -> Dict[str, Any]:
    """Safe answers when Chroma / RAG cannot run."""
    q = (query or "").strip()
    hint = (
        "This service is running without a loaded vector index. "
        "Add Chroma data under `data/indexed/` (or set INDEXED_DATA_PATH) and redeploy. "
        "For official information visit https://www.hdfcfund.com/"
    )
    if not q:
        return {"answer": "Please enter a question.", "status": "error"}
    return {
        "answer": (
            f"I can't search the fund corpus right now ({hint}). "
            f"Your question was: «{q[:200]}»."
        ),
        "source": None,
        "source_link": "https://www.hdfcfund.com/",
        "last_updated": None,
        "status": "degraded",
    }


def _vector_fetch_k() -> int:
    vk = _int_env("VECTOR_FETCH_K", 10, 4, 24)
    alt = _str_env("STREAMLIT_VECTOR_FETCH_K", "")
    if alt:
        try:
            vk = max(4, min(int(alt), 24))
        except ValueError:
            pass
    return vk


def ensure_rag_engine() -> None:
    """
    Lazy-init full RAG once. On failure: degraded mode, no crash.
    Does not run at import time or before first query.
    """
    global rag_orchestrator, _chroma_loaded
    global _rag_init_attempted, _rag_init_error, _degraded_no_rag

    if rag_orchestrator is not None or _degraded_no_rag:
        return

    with _rag_init_lock:
        if rag_orchestrator is not None or _degraded_no_rag:
            return
        _rag_init_attempted = True
        try:
            before = _memory_mb()
            logger.info("Lazy-loading RAG orchestrator (before ~%.1f MB)", before or -1)

            from orchestrator import RAGOrchestrator

            indexed_data_path = _indexed_dir()
            use_bm25 = _bool_env("USE_BM25", False)
            use_reranker = _bool_env("USE_RERANKER", False)
            vk = _vector_fetch_k()

            rag_orchestrator = RAGOrchestrator(
                persist_directory=indexed_data_path,
                scheme_names=_schemes,
                use_bm25=use_bm25,
                use_reranker=use_reranker,
                vector_fetch_k=vk,
            )
            _chroma_loaded = True
            gc.collect()
            after = _memory_mb()
            logger.info("RAG orchestrator ready (after ~%.1f MB)", after or -1)
        except Exception as e:
            _rag_init_error = str(e)
            _degraded_no_rag = True
            logger.warning(
                "RAG / Chroma initialization failed — entering degraded mode (no crash): %s",
                e,
                exc_info=True,
            )


def _run_query_sync(query: str) -> Dict[str, Any]:
    if rag_orchestrator is None:
        return _fallback_query_response(query)
    out = rag_orchestrator.answer_query(query)
    global _model_loaded
    _model_loaded = True  # embedding path exercised after first successful answer
    gc.collect()
    return out


def _build_health_response() -> HealthResponse:
    mock_mode = not _has_groq_key()
    degraded = _degraded_no_rag
    if rag_orchestrator is not None:
        msg = "RAG online"
        if mock_mode:
            msg += " · LLM mock (set GROQ_API_KEY for Groq)"
    elif _degraded_no_rag:
        msg = "Degraded: index unavailable — placeholder answers only"
        if _rag_init_error:
            msg += f" ({_rag_init_error[:120]})"
    else:
        msg = "API ready — RAG loads on first query"

    return HealthResponse(
        status="healthy",
        ready=_api_ready,
        message=msg,
        schemes_loaded=len(_schemes),
        memory_mb=_memory_mb(),
        model_loaded=_model_loaded,
        chroma_loaded=_chroma_loaded,
        mock_mode=mock_mode,
        degraded=degraded,
    )


def _health_safe() -> HealthResponse:
    try:
        return _build_health_response()
    except Exception as e:
        logger.exception("Health aggregation failed: %s", e)
        return HealthResponse(
            status="healthy",
            ready=True,
            message="Health readout degraded internally; process is up.",
            schemes_loaded=0,
            memory_mb=None,
            model_loaded=False,
            chroma_loaded=False,
            mock_mode=True,
            degraded=True,
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _schemes, _api_ready
    logger.info(
        "HDFC MF API boot — BASE=%s RAM=%.1f MB",
        BASE,
        _memory_mb() or -1,
    )
    try:
        _schemes = _load_schemes_only()
    except Exception:
        logger.exception("Scheme load failed; continuing with empty schemes")
        _schemes = []

    _api_ready = True
    mem = _memory_mb()
    logger.info(
        "Startup complete — api_ready=True schemes=%s mock_llm=%s RAM=%.1f MB",
        len(_schemes),
        not _has_groq_key(),
        mem or -1,
    )
    yield
    logger.info("HDFC MF API shutdown")


app = FastAPI(
    title="HDFC Mutual Fund API",
    description="Production RAG API",
    version="2.1.0",
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
    return _health_safe()


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Never raises; always JSON-serializable."""
    return _health_safe()


@app.get("/schemes", response_model=SchemesResponse)
async def get_schemes():
    try:
        return SchemesResponse(schemes=_schemes)
    except Exception:
        return SchemesResponse(schemes=[])


@app.post("/query", response_model=QueryResponse)
async def query_fund(request: QueryRequest):
    q = (request.query or "").strip()
    if not q:
        return QueryResponse(answer="Please enter a question.", status="error")

    timeout_s = max(5.0, min(_float_env("QUERY_TIMEOUT_SECONDS", 90.0), 300.0))

    try:
        await asyncio.to_thread(ensure_rag_engine)
    except Exception:
        logger.exception("ensure_rag_engine failed")

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
            answer="The request took too long. Try again with a shorter question.",
            status="timeout",
        )
    except Exception:
        logger.exception("Query failed")
        return QueryResponse(
            answer=_fallback_query_response(q)["answer"],
            status="error",
        )


@app.post("/chat", response_model=QueryResponse)
async def chat_with_history(request: QueryRequest):
    return await query_fund(request)


if __name__ == "__main__":
    import uvicorn

    host = _str_env("HOST", "0.0.0.0") or "0.0.0.0"
    port = _int_env("PORT", 8000, 1, 65535)
    uvicorn.run(
        "backend.app:app",
        host=host,
        port=port,
        workers=1,
        reload=False,
        log_level=_str_env("LOG_LEVEL", "info").lower() or "info",
    )
