"""
HDFC Mutual Fund Assistant — FastAPI production API (Railway / Docker).
Boots with zero env vars; RAG is lazy; failures → degraded answers, never stuck ready=false.
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
_chroma_loaded: bool = False
_model_loaded: bool = False
_rag_init_attempted: bool = False
_rag_init_error: Optional[str] = None
_degraded_no_rag: bool = False
_rag_init_timed_out: bool = False


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
    """`ready` = HTTP API live. `rag_available` = Chroma+RAGOrchestrator up. `rag_ready` = first retrieval done."""

    status: str = Field(default="healthy")
    ready: bool = Field(default=True)
    rag_available: bool = Field(default=False)
    rag_ready: bool = Field(
        default=False,
        description="True after first successful embedding-backed query (not just Chroma open).",
    )
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


def _fallback_query_response(query: str, *, reason: str = "unavailable") -> Dict[str, Any]:
    """Safe answers when Chroma / RAG cannot run or timed out."""
    q = (query or "").strip()
    if not q:
        return {"answer": "Please enter a question.", "status": "error"}

    if reason == "timeout":
        body = (
            "The AI retrieval layer is still warming up or the last request hit a time limit. "
            "Please wait a few seconds and try again with a shorter question. "
            "Official fund information: https://www.hdfcfund.com/"
        )
    elif reason == "query_timeout":
        body = (
            "That request took too long to complete. The service may be under load or still "
            "loading models. Try again in a moment. Official information: https://www.hdfcfund.com/"
        )
    else:
        body = (
            "The full RAG index is not available on this deployment (Chroma/embeddings could not "
            "be initialized). Add indexed data under `data/indexed/` or set INDEXED_DATA_PATH. "
            "Official information: https://www.hdfcfund.com/"
        )

    return {
        "answer": f"{body}\n\n(Your question: «{q[:200]}»)",
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


def _sync_init_rag_body() -> None:
    """Heavy RAG init (Chroma client, collection). Runs in worker thread; no asyncio here."""
    global rag_orchestrator, _chroma_loaded, _rag_init_error, _degraded_no_rag, _rag_init_timed_out

    if rag_orchestrator is not None:
        return
    if _rag_init_timed_out:
        logger.info("Skipping RAG init — previous attempt timed out (fallback active).")
        return

    before = _memory_mb()
    logger.info(
        "RAG init thread start — RAM ~%.1f MB | protobuf_impl=%s",
        before or -1,
        os.environ.get("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "(unset)"),
    )

    try:
        from orchestrator import RAGOrchestrator

        indexed_data_path = _indexed_dir()
        logger.info("Chroma persist path: %s", indexed_data_path)

        use_bm25 = _bool_env("USE_BM25", False)
        use_reranker = _bool_env("USE_RERANKER", False)
        vk = _vector_fetch_k()

        orch = RAGOrchestrator(
            persist_directory=indexed_data_path,
            scheme_names=_schemes,
            use_bm25=use_bm25,
            use_reranker=use_reranker,
            vector_fetch_k=vk,
        )

        if _rag_init_timed_out:
            logger.warning(
                "RAG init finished after timeout — discarding orchestrator to stay in fallback mode."
            )
            return

        rag_orchestrator = orch
        _chroma_loaded = True
        gc.collect()
        after = _memory_mb()
        logger.info("Chroma index loaded successfully — collection mf_faq_corpus is reachable.")
        logger.info(
            "RAG initialized successfully — orchestrator attached (RAM ~%.1f MB; embeddings load on first query).",
            after or -1,
        )
    except Exception as e:
        err = str(e)
        _rag_init_error = err
        _degraded_no_rag = True
        logger.warning(
            "Index missing or invalid — RAG / Chroma init FAILED (rebuild: python scripts/rebuild_chroma_from_chunks.py --force). "
            "Error type=%s msg=%s",
            type(e).__name__,
            err[:500],
            exc_info=True,
        )
        if "protobuf" in err.lower() or "descriptor" in err.lower():
            logger.warning(
                "Possible protobuf/grpc issue — try PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python "
                "(already defaulted in app bootstrap)."
            )


async def ensure_rag_engine_async(request: Request) -> None:
    """
    Lazy-init RAG with hard wall clock. Never blocks forever.
    Serialised per-process via app.state.rag_lock.
    """
    global _rag_init_attempted, _degraded_no_rag, _rag_init_error, _rag_init_timed_out

    if rag_orchestrator is not None:
        return
    if _degraded_no_rag and _rag_init_attempted:
        return

    lock = request.app.state.rag_lock
    # First init downloads MiniLM + opens Chroma — default 120s for cold Railway
    init_timeout = max(5.0, min(_float_env("RAG_INIT_TIMEOUT_SECONDS", 120.0), 600.0))

    async with lock:
        if rag_orchestrator is not None:
            return
        if _degraded_no_rag and _rag_init_attempted:
            return

        _rag_init_attempted = True
        logger.info(
            "Starting bounded RAG init (max %.0fs) | groq_key_present=%s",
            init_timeout,
            _has_groq_key(),
        )

        try:
            async with asyncio.timeout(init_timeout):
                await asyncio.to_thread(_sync_init_rag_body)
        except TimeoutError:
            _rag_init_timed_out = True
            _degraded_no_rag = True
            _rag_init_error = _rag_init_error or f"init exceeded {init_timeout:.0f}s"
            logger.warning(
                "RAG_INIT_TIMEOUT — skipping heavy stack; degraded mode ON (%.0fs)",
                init_timeout,
            )
        except Exception:
            logger.exception("ensure_rag_engine_async outer failure")
            _degraded_no_rag = True
            _rag_init_error = _rag_init_error or "async init wrapper failed"


def _run_query_sync(query: str) -> Dict[str, Any]:
    if rag_orchestrator is None:
        return _fallback_query_response(query, reason="unavailable")
    try:
        out = rag_orchestrator.answer_query(query)
    except Exception as e:
        logger.exception("answer_query failed: %s", e)
        return _fallback_query_response(query, reason="unavailable")

    global _model_loaded
    _model_loaded = True
    logger.info("Query path OK — embedding/LLM stack exercised")
    gc.collect()
    return out


def _build_health_response() -> HealthResponse:
    mock_mode = not _has_groq_key()
    rag_available = rag_orchestrator is not None
    degraded = not rag_available and (_degraded_no_rag or _rag_init_timed_out)

    if rag_available:
        msg = "Full RAG available"
        if mock_mode:
            msg += " · LLM in demo mode (set GROQ_API_KEY for Groq)"
    elif _rag_init_timed_out:
        msg = "Fallback mode: RAG init timed out — placeholder answers"
    elif _degraded_no_rag:
        msg = "Fallback mode: RAG unavailable — placeholder answers"
        if _rag_init_error:
            msg += f" ({_rag_init_error[:100]})"
    else:
        msg = "API up — RAG loads on first question (bounded init)"

    return HealthResponse(
        status="healthy",
        ready=True,
        rag_available=rag_available,
        rag_ready=_model_loaded,
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
            rag_available=False,
            rag_ready=False,
            message="Health readout failed internally; process is up.",
            schemes_loaded=0,
            memory_mb=None,
            model_loaded=False,
            chroma_loaded=False,
            mock_mode=True,
            degraded=True,
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _schemes
    app.state.rag_lock = asyncio.Lock()

    logger.info(
        "HDFC MF API boot — BASE=%s RAM=%.1f MB | protobuf=%s | groq_key=%s",
        BASE,
        _memory_mb() or -1,
        os.environ.get("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "(unset)"),
        "yes" if _has_groq_key() else "no (mock LLM when RAG runs)",
    )
    try:
        _schemes = _load_schemes_only()
    except Exception:
        logger.exception("Scheme load failed; continuing with empty schemes")
        _schemes = []

    mem = _memory_mb()
    logger.info(
        "Startup complete — routes live, RAG deferred | schemes=%s RAM=%.1f MB | "
        "mock_mode in /health means missing GROQ_API_KEY only (not Chroma).",
        len(_schemes),
        mem or -1,
    )
    yield
    logger.info("HDFC MF API shutdown")


app = FastAPI(
    title="HDFC Mutual Fund API",
    description="Production RAG API",
    version="2.2.0",
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
    """Never raises; `ready` always true when this handler runs."""
    return _health_safe()


@app.get("/schemes", response_model=SchemesResponse)
async def get_schemes():
    try:
        return SchemesResponse(schemes=_schemes)
    except Exception:
        return SchemesResponse(schemes=[])


@app.post("/query", response_model=QueryResponse)
async def query_fund(request: Request, body: QueryRequest):
    q = (body.query or "").strip()
    if not q:
        return QueryResponse(answer="Please enter a question.", status="error")

    query_timeout_s = max(5.0, min(_float_env("QUERY_TIMEOUT_SECONDS", 90.0), 300.0))

    try:
        await ensure_rag_engine_async(request)
    except Exception:
        logger.exception("ensure_rag_engine_async failed")

    try:
        async with asyncio.timeout(query_timeout_s):
            response = await asyncio.to_thread(_run_query_sync, q)
        return QueryResponse(
            answer=response.get("answer", "") or "No answer returned.",
            source=response.get("source"),
            source_link=response.get("source_link"),
            last_updated=response.get("last_updated"),
            status=response.get("status", "error"),
        )
    except TimeoutError:
        logger.warning("Query timed out after %ss", query_timeout_s)
        fb = _fallback_query_response(q, reason="query_timeout")
        return QueryResponse(answer=fb["answer"], status="timeout")
    except Exception:
        logger.exception("Query failed")
        fb = _fallback_query_response(q, reason="unavailable")
        return QueryResponse(answer=fb["answer"], status="error")


@app.post("/chat", response_model=QueryResponse)
async def chat_with_history(request: Request, body: QueryRequest):
    return await query_fund(request, body)


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
