"""
HDFC Mutual Fund Assistant — FastAPI production API (Railway / Docker).
Boots with zero env vars; RAG is lazy; failures → degraded answers, never stuck ready=false.

Paths: all data paths resolve against the package root (directory containing `backend/`), never cwd.
"""

from __future__ import annotations

import asyncio
import gc
import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
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

# backend/app.py -> Milestone2/ (single source of truth for data paths — independent of process cwd)
BASE_DIR: Path = Path(__file__).resolve().parent.parent
BASE: str = str(BASE_DIR)
sys.path.insert(0, str(BASE_DIR / "phase2_retrieval_layer" / "src"))
sys.path.insert(0, str(BASE_DIR / "phase3_reasoning_guardrails" / "src"))

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
    """Explicit os.getenv — Railway injects GROQ_API_KEY; never log the value."""
    return bool((os.getenv("GROQ_API_KEY") or "").strip())


def _resolve_data_path(env_name: str, default_relative: str) -> str:
    """
    Resolve INDEXED_DATA_PATH / PROCESSED_DATA_PATH against BASE_DIR when relative.
    Railway cwd may not be Milestone2; relative env values must not depend on cwd.
    """
    raw = _str_env(env_name, "")
    if not raw:
        return str((BASE_DIR / default_relative).resolve())
    p = Path(raw)
    if p.is_absolute():
        return str(p.resolve())
    return str((BASE_DIR / p).resolve())


def _indexed_dir() -> str:
    return _resolve_data_path("INDEXED_DATA_PATH", "data/indexed")


def _processed_dir() -> str:
    return _resolve_data_path("PROCESSED_DATA_PATH", "data/processed")


def _chroma_index_on_disk() -> bool:
    """Lightweight check — no Chroma import. True if persistent DB file is present."""
    try:
        return (Path(_indexed_dir()) / "chroma.sqlite3").is_file()
    except Exception:
        return False


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
_retrieval_warmed: bool = False
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
    """ready=API up; rag_available=orchestrator up; rag_ready=retrieval+embeddings warmed."""

    status: str = Field(default="healthy")
    ready: bool = Field(default=True)
    rag_available: bool = Field(default=False)
    rag_ready: bool = Field(
        default=False,
        description="True after embedding model loaded and one vector search succeeded (or full /query).",
    )
    message: str = Field(default="")
    schemes_loaded: int = Field(default=0)
    memory_mb: Optional[float] = None
    model_loaded: bool = Field(
        default=False,
        description="True after first successful answer_query (includes LLM / generator path).",
    )
    chroma_loaded: bool = Field(default=False)
    mock_mode: bool = Field(default=True)
    degraded: bool = Field(default=False)
    index_on_disk: bool = Field(
        default=False,
        description="True if chroma.sqlite3 exists at resolved INDEXED_DATA_PATH.",
    )


def _load_schemes_only() -> List[str]:
    processed = _processed_dir()
    chunked_data_path = str(Path(processed) / "chunked_data_phase1.4.json")
    if not os.path.exists(chunked_data_path):
        logger.warning("Chunked data missing at %s — schemes list empty.", chunked_data_path)
        return []
    try:
        with open(chunked_data_path, "r", encoding="utf-8") as f:
            chunks = json.load(f)
        schemes = sorted({c["scheme_name"] for c in chunks})
        logger.info("Loaded %s scheme names from %s", len(schemes), chunked_data_path)
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
    global rag_orchestrator, _chroma_loaded, _rag_init_error, _degraded_no_rag, _rag_init_timed_out, _retrieval_warmed

    if rag_orchestrator is not None:
        logger.info("RAG init skipped — orchestrator already present.")
        return
    if _rag_init_timed_out:
        logger.info("Skipping RAG init — previous attempt timed out (fallback active).")
        return

    before = _memory_mb()
    logger.info(
        "RAG init thread start — BASE_DIR=%s | cwd=%s | indexed=%s | RAM ~%.1f MB | protobuf_impl=%s",
        BASE_DIR,
        os.getcwd(),
        _indexed_dir(),
        before or -1,
        os.environ.get("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "(unset)"),
    )

    try:
        from orchestrator import RAGOrchestrator

        indexed_data_path = _indexed_dir()
        logger.info("Chroma persist path (resolved): %s | exists=%s", indexed_data_path, os.path.isdir(indexed_data_path))

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
            "RAG initialized successfully — orchestrator attached (RAM ~%.1f MB).",
            after or -1,
        )

        if _bool_env("RAG_EMBEDDING_WARM", True):
            try:
                orch.warm_retrieval_stack()
                _retrieval_warmed = True
                mem2 = _memory_mb()
                logger.info(
                    "Embedding + retrieval warm complete — rag_ready on /health (RAM ~%.1f MB).",
                    mem2 or -1,
                )
            except Exception as e_w:
                logger.warning(
                    "Embedding warm failed (orchestrator still usable on first /query): type=%s msg=%s",
                    type(e_w).__name__,
                    str(e_w)[:400],
                    exc_info=True,
                )
        gc.collect()
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


async def ensure_rag_engine_async_from_app(app: FastAPI) -> None:
    """
    Lazy-init RAG with hard wall clock. Never blocks forever.
    Serialised per-process via app.state.rag_lock.
    """
    global _rag_init_attempted, _degraded_no_rag, _rag_init_error, _rag_init_timed_out

    if rag_orchestrator is not None:
        return
    if _degraded_no_rag and _rag_init_attempted:
        return

    lock = app.state.rag_lock
    init_timeout = max(5.0, min(_float_env("RAG_INIT_TIMEOUT_SECONDS", 120.0), 600.0))

    async with lock:
        if rag_orchestrator is not None:
            return
        if _degraded_no_rag and _rag_init_attempted:
            return

        _rag_init_attempted = True
        groq_present = _has_groq_key()
        logger.info(
            "Starting bounded RAG init (max %.0fs) | groq_key_present=%s (from os.getenv GROQ_API_KEY, value not logged)",
            init_timeout,
            groq_present,
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


async def ensure_rag_engine_async(request: Request) -> None:
    await ensure_rag_engine_async_from_app(request.app)


def _run_query_sync(query: str) -> Dict[str, Any]:
    if rag_orchestrator is None:
        logger.warning("_run_query_sync: no orchestrator — returning fallback")
        return _fallback_query_response(query, reason="unavailable")
    try:
        logger.info("Running answer_query (first call may load MiniLM embeddings)…")
        out = rag_orchestrator.answer_query(query)
    except Exception as e:
        logger.exception("answer_query failed: %s", e)
        return _fallback_query_response(query, reason="unavailable")

    global _model_loaded, _retrieval_warmed
    _model_loaded = True
    _retrieval_warmed = True
    logger.info("Query path OK — embedding/LLM stack exercised; /health model_loaded + rag_ready")
    gc.collect()
    return out


def _build_health_response() -> HealthResponse:
    mock_mode = not _has_groq_key()
    rag_available = rag_orchestrator is not None
    degraded = not rag_available and (_degraded_no_rag or _rag_init_timed_out)
    index_on_disk = _chroma_index_on_disk()

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
    elif index_on_disk:
        msg = (
            "Chroma index on disk; RAG should attach via background warm or first POST /query. "
            "If this persists, check logs for RAG init errors."
        )
        if mock_mode:
            msg += " mock_mode=true means GROQ_API_KEY is unset (LLM demo when RAG runs)."
    else:
        msg = (
            "No chroma.sqlite3 at resolved INDEXED_DATA_PATH — clone may be missing data/indexed/ "
            "or path is wrong. Rebuild: python scripts/rebuild_chroma_from_chunks.py --force"
        )
        if mock_mode:
            msg += " (mock_mode only reflects missing GROQ_API_KEY.)"

    return HealthResponse(
        status="healthy",
        ready=True,
        rag_available=rag_available,
        rag_ready=_retrieval_warmed,
        message=msg,
        schemes_loaded=len(_schemes),
        memory_mb=_memory_mb(),
        model_loaded=_model_loaded,
        chroma_loaded=_chroma_loaded,
        mock_mode=mock_mode,
        degraded=degraded,
        index_on_disk=index_on_disk,
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
            mock_mode=not _has_groq_key(),
            degraded=True,
            index_on_disk=_chroma_index_on_disk(),
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _schemes
    app.state.rag_lock = asyncio.Lock()

    groq_present = _has_groq_key()
    logger.info(
        "HDFC MF API boot — BASE_DIR=%s | cwd=%s | groq_key_present=%s (GROQ_API_KEY via os.getenv, not logged) | protobuf=%s",
        BASE_DIR,
        os.getcwd(),
        groq_present,
        os.environ.get("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "(unset)"),
    )
    logger.info(
        "Resolved paths — indexed=%s | processed=%s | index_on_disk=%s",
        _indexed_dir(),
        _processed_dir(),
        _chroma_index_on_disk(),
    )
    try:
        _schemes = _load_schemes_only()
    except Exception:
        logger.exception("Scheme load failed; continuing with empty schemes")
        _schemes = []

    mem = _memory_mb()
    logger.info(
        "Startup complete — routes live | schemes=%s RAM=%.1f MB | "
        "mock_mode on /health = not groq_key_present.",
        len(_schemes),
        mem or -1,
    )

    # Warm Chroma + orchestrator in the background so /health shows rag_available without
    # requiring a synthetic first /query (Railway probes often only hit /health).
    warm = _bool_env("RAG_BACKGROUND_WARM", True)
    if warm and _chroma_index_on_disk():

        async def _background_rag_warm() -> None:
            try:
                logger.info("Background RAG warm task started (non-blocking).")
                await ensure_rag_engine_async_from_app(app)
                if rag_orchestrator is not None:
                    logger.info("Background RAG warm completed — orchestrator ready.")
                else:
                    logger.warning(
                        "Background RAG warm finished without orchestrator (degraded=%s err=%s)",
                        _degraded_no_rag,
                        (_rag_init_error or "")[:200],
                    )
            except Exception:
                logger.exception("Background RAG warm task failed")

        asyncio.create_task(_background_rag_warm())
    elif warm and not _chroma_index_on_disk():
        logger.info("RAG_BACKGROUND_WARM=true but no chroma.sqlite3 — skipping background warm.")

    yield
    logger.info("HDFC MF API shutdown")


app = FastAPI(
    title="HDFC Mutual Fund API",
    description="Production RAG API",
    version="2.2.4",
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

    # First request: RAG init (bounded) + answer — allow enough wall time for both phases
    init_timeout = max(5.0, min(_float_env("RAG_INIT_TIMEOUT_SECONDS", 120.0), 600.0))
    query_timeout_s = max(5.0, min(_float_env("QUERY_TIMEOUT_SECONDS", 90.0), 300.0))
    combined_ceiling = min(600.0, init_timeout + query_timeout_s + 30.0)

    logger.info("POST /query — begin RAG lazy init if needed, then answer (combined ceiling ~%.0fs)", combined_ceiling)

    try:
        async with asyncio.timeout(combined_ceiling):
            await ensure_rag_engine_async(request)
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
        logger.warning("POST /query timed out (combined init+answer ceiling ~%.0fs)", combined_ceiling)
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
