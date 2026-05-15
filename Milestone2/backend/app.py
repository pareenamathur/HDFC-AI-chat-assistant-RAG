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
import math
import os
import sys
import traceback
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.corpus_diagnostics import build_freshness_report

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


_DEFAULT_LOCAL_ORIGINS = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
)

_DEFAULT_VERCEL_ORIGIN_REGEX = r"https://([a-z0-9-]+\.)*vercel\.app"


def _configure_cors(app: FastAPI) -> None:
    """
    Browser-safe CORS for Vercel + local Next.js.
    Do not combine allow_origins=['*'] with allow_credentials=True (browsers block it).
    """
    raw = _str_env("CORS_ALLOW_ORIGINS", "")
    regex = _str_env("CORS_ALLOW_ORIGIN_REGEX", _DEFAULT_VERCEL_ORIGIN_REGEX)
    credentials = _bool_env("CORS_ALLOW_CREDENTIALS", False)

    if not raw or raw.strip() == "*":
        origins = list(_DEFAULT_LOCAL_ORIGINS)
        origin_regex = regex
    else:
        origins = [x.strip() for x in raw.split(",") if x.strip()]
        for o in _DEFAULT_LOCAL_ORIGINS:
            if o not in origins:
                origins.append(o)
        origin_regex = regex or None

    logger.info(
        "CORS configured — allow_origins=%s allow_origin_regex=%s allow_credentials=%s",
        origins,
        origin_regex or "(none)",
        credentials,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_origin_regex=origin_regex,
        allow_credentials=credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )


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


def _log_index_diagnostics() -> None:
    """Startup visibility for Railway path / index layout (no secrets)."""
    idx = Path(_indexed_dir()).resolve()
    sqlite = idx / "chroma.sqlite3"
    logger.info(
        "RAG index diagnostics — BASE_DIR=%s | INDEXED_DATA_PATH absolute=%s | chroma.sqlite3 exists=%s",
        BASE_DIR.resolve(),
        idx,
        sqlite.is_file(),
    )
    if sqlite.is_file():
        try:
            sz = sqlite.stat().st_size
            logger.info("chroma.sqlite3 size_bytes=%s (~%.2f MB)", sz, sz / (1024 * 1024))
        except OSError as e:
            logger.warning("Could not stat chroma.sqlite3: %s", e)
    try:
        if idx.is_dir():
            entries = list(idx.iterdir())
            names = sorted(p.name for p in entries)
            logger.info("indexed_dir top-level entry count=%s names=%s", len(names), names[:40])
            seg_dirs = [n for n in names if len(n) == 36 and "-" in n]
            logger.info("Chroma segment-style UUID dirs count=%s", len(seg_dirs))
        else:
            logger.warning("indexed_dir is not a directory: %s", idx)
    except Exception as e:
        logger.warning("Could not list indexed_dir: %s", e)

    proc = Path(_processed_dir()).resolve()
    chunk = proc / "chunked_data_phase1.4.json"
    logger.info(
        "processed corpus — absolute=%s | chunked_data_phase1.4.json exists=%s",
        proc,
        chunk.is_file(),
    )
    logger.info(
        ".gitignore: data/indexed/chroma.sqlite3 is NOT ignored (only *.tmp / .DS_Store under data/indexed/). "
        "Commit index files for Railway."
    )
    _log_corpus_freshness_diagnostics()


def _log_corpus_freshness_diagnostics() -> None:
    """Manifest, NAV as-of dates, and index mtime — surfaces stale clone vs stale Groww scrape."""
    try:
        report = build_freshness_report(BASE_DIR)
    except Exception as e:
        logger.warning("Corpus freshness diagnostics failed: %s", e)
        return

    logger.info(
        "Corpus manifest — last_updated=%s source=%s embedding=%s chunks(manifest=%s file=%s)",
        report.get("manifest_last_updated"),
        report.get("manifest_source"),
        report.get("manifest_embedding_model"),
        report.get("chunks_total_manifest"),
        report.get("chunks_total_file"),
    )
    logger.info(
        "Corpus NAV — dates_in_chunks=%s | as_of_min=%s as_of_max=%s age_days=%s",
        report.get("nav_dates_found"),
        report.get("nav_as_of_min"),
        report.get("nav_as_of_max"),
        report.get("nav_age_days"),
    )
    logger.info(
        "Chroma on disk — mtime_utc=%s size_bytes=%s",
        report.get("chroma_sqlite_mtime_utc"),
        report.get("chroma_sqlite_size_bytes"),
    )
    if report.get("embedding_model_mismatch"):
        logger.warning(
            "Corpus embedding_model=%s does not match runtime MiniLM (%s). "
            "Run scripts/run_corpus_refresh.py and git pull data/indexed/.",
            report.get("manifest_embedding_model"),
            report.get("expected_embedding_model"),
        )
    manifest_ts = report.get("manifest_last_updated")
    chroma_ts = report.get("chroma_sqlite_mtime_utc")
    if manifest_ts and chroma_ts:
        try:
            m_dt = datetime.fromisoformat(str(manifest_ts).replace("Z", "+00:00"))
            c_dt = datetime.fromisoformat(str(chroma_ts).replace("Z", "+00:00"))
            if c_dt < m_dt:
                logger.warning(
                    "chroma.sqlite3 mtime (%s) is older than corpus_version last_updated (%s) — "
                    "git pull Milestone2/data/indexed/ or rebuild Chroma locally.",
                    chroma_ts,
                    manifest_ts,
                )
        except ValueError:
            pass
    if report.get("nav_stale_warning"):
        logger.warning(
            "NAV in corpus is stale (newest as_of=%s, %s days old, threshold=%s). "
            "Index may be fresh but Groww HTML still shows old NAV — check fetch 404s and data/html/.",
            report.get("nav_as_of_max"),
            report.get("nav_age_days"),
            report.get("stale_nav_threshold_days"),
        )


def _sync_chroma_sqlite_probe() -> None:
    """
    Lightweight Chroma open + collection count before full RAG init.
    Surfaces missing DB / wrong path / empty collection in logs independently of orchestrator.
    """
    path = str(Path(_indexed_dir()).resolve())
    sqlite = Path(path) / "chroma.sqlite3"
    if not sqlite.is_file():
        logger.warning("STARTUP_CHROMA_PROBE skip — chroma.sqlite3 missing at %s", path)
        return
    try:
        import chromadb

        client = chromadb.PersistentClient(path=path)
        coll = client.get_collection(name="mf_faq_corpus")
        n = coll.count()
        logger.info('Chroma collection opened (probe) — name="mf_faq_corpus" document_count=%s', n)
        if n == 0:
            logger.error(
                "STARTUP_CHROMA_PROBE: collection empty — rebuild locally: "
                "python scripts/rebuild_chroma_from_chunks.py --force then commit data/indexed/ and redeploy."
            )
        else:
            logger.info("RAG index integrity check passed — Chroma mf_faq_corpus readable (probe).")
    except Exception:
        logger.exception(
            "STARTUP_CHROMA_PROBE failed — corrupt index, wrong path, or Chroma mismatch. "
            "Recovery: rebuild index, re-commit data/indexed/, redeploy Railway."
        )


def _memory_mb() -> Optional[float]:
    try:
        import psutil

        return psutil.Process().memory_info().rss / 1024 / 1024
    except Exception:
        return None


# Bumped with health/query semantics changes; keep in sync with FastAPI `version=`.
APP_VERSION = "2.2.17"

# --- Runtime state (lazy RAG + degradation) ---
rag_orchestrator: Any = None
_schemes: List[str] = []
_chroma_loaded: bool = False
_model_loaded: bool = False
_retrieval_warmed: bool = False
_rag_init_attempted: bool = False
_rag_init_error: Optional[str] = None
_degraded_no_rag: bool = False
_rag_init_timed_out: bool = False
# True after a POST /query ends in degraded fallback, timeout, or handler error (until a successful pipeline run).
_last_query_pipeline_degraded: bool = False
# Last completed POST /query status (normalized lower-case), for /health transparency.
_last_query_status_report: Optional[str] = None


def _safe_memory_mb() -> Optional[float]:
    """RSS in MB; never NaN/Inf (invalid in strict JSON)."""
    m = _memory_mb()
    if m is None:
        return None
    try:
        if math.isnan(m) or math.isinf(m):
            return None
        return round(float(m), 2)
    except (TypeError, ValueError):
        return None


def _record_last_query_status(status: str) -> None:
    """Align /health `degraded` with real /query outcomes (not only RAG init)."""
    global _last_query_pipeline_degraded, _last_query_status_report
    s = (status or "").strip().lower()
    _last_query_status_report = s if s else "error"
    if s in ("success", "refusal", "no_results"):
        _last_query_pipeline_degraded = False
    elif s in ("degraded", "timeout", "error"):
        _last_query_pipeline_degraded = True
    else:
        logger.warning("Unknown POST /query status %r — marking query pipeline degraded for /health", status)
        _last_query_pipeline_degraded = True


class QueryRequest(BaseModel):
    query: str
    chat_history: List[Dict[str, str]] = []


class SourceRef(BaseModel):
    title: str
    url: str
    scheme_name: Optional[str] = None
    nav_as_of: Optional[str] = None


class QueryResponse(BaseModel):
    answer: str
    source: Optional[str] = None
    source_link: Optional[str] = None
    last_updated: Optional[str] = None
    sources: List[SourceRef] = Field(default_factory=list)
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
        description="True once SentenceTransformer is loaded and retrieval is operational (warm or first /query).",
    )
    chroma_loaded: bool = Field(default=False)
    mock_mode: bool = Field(default=True)
    degraded: bool = Field(
        default=False,
        description="True if RAG init failed/timed out OR the last POST /query ended in error/timeout/degraded fallback.",
    )
    index_on_disk: bool = Field(
        default=False,
        description="True if chroma.sqlite3 exists at resolved INDEXED_DATA_PATH.",
    )
    api_version: str = Field(
        default=APP_VERSION,
        description="Backend build version string (same family as OpenAPI /version).",
    )
    last_query_status: Optional[str] = Field(
        default=None,
        description="Normalized status of the last completed POST /query on this worker (null if none yet).",
    )
    corpus_last_updated: Optional[str] = Field(
        default=None,
        description="data/corpus_version.json last_updated (UTC) if present.",
    )
    nav_as_of_max: Optional[str] = Field(
        default=None,
        description="Newest NAV date found in chunked corpus (ISO date), if any.",
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

    if reason in ("no_orchestrator", "query_failed", "unavailable"):
        logger.warning(
            "FALLBACK_RESPONSE reason=%s query_preview=%r\n%s",
            reason,
            q[:120],
            "".join(traceback.format_stack(limit=18)),
        )

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
    elif reason == "no_orchestrator":
        body = (
            "The RAG engine is not attached (initialization may still be running, timed out, or failed). "
            "Check Railway logs for RAG_INIT_TIMEOUT / STARTUP_CHROMA_PROBE / Chroma errors. "
            "Official information: https://www.hdfcfund.com/"
        )
    elif reason == "query_failed":
        body = (
            "The retrieval pipeline hit an error while processing your question (the index may be fine — "
            "see server logs for answer_query traceback). Try rephrasing or retry. "
            "Official information: https://www.hdfcfund.com/"
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
    global rag_orchestrator, _chroma_loaded, _rag_init_error, _degraded_no_rag, _rag_init_timed_out, _retrieval_warmed, _model_loaded

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

        try:
            n_docs = orch.retriever.collection.count()
            logger.info("Chroma collection mf_faq_corpus count=%s (post-init)", n_docs)
            if n_docs == 0:
                logger.warning(
                    "Chroma collection is empty — rebuild index: python scripts/rebuild_chroma_from_chunks.py --force"
                )
        except Exception as cnt_e:
            logger.warning("Could not read Chroma collection count: %s", cnt_e)

        if len(_schemes) == 0:
            logger.warning(
                "SCHEME LIST IS EMPTY — fund-name filters will be skipped until "
                "data/processed/chunked_data_phase1.4.json is available (PROCESSED_DATA_PATH=%s). "
                "POST /query used to fail here when thefuzz received an empty choice list.",
                _processed_dir(),
            )

        if _bool_env("RAG_EMBEDDING_WARM", True):
            try:
                orch.warm_retrieval_stack()
                _retrieval_warmed = True
                _model_loaded = True
                mem2 = _memory_mb()
                logger.info("Embedding model loaded successfully for retrieval (SentenceTransformer + probe search).")
                logger.info(
                    "model_loaded set to True — embedding stack operational (RAM ~%.1f MB). /health rag_ready + model_loaded.",
                    mem2 or -1,
                )
                logger.info("RAG index integrity check passed — probe vector search completed.")
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
        logger.warning("_run_query_sync: no orchestrator — returning fallback (reason=no_orchestrator)")
        return _fallback_query_response(query, reason="no_orchestrator")
    try:
        logger.info(
            "Running answer_query — schemes=%s indexed=%s query_len=%s",
            len(_schemes),
            _indexed_dir(),
            len((query or "").strip()),
        )
        out = rag_orchestrator.answer_query(query)
    except Exception as e:
        logger.exception(
            "answer_query failed — schemes=%s processed_json=%s err_type=%s",
            len(_schemes),
            Path(_processed_dir()) / "chunked_data_phase1.4.json",
            type(e).__name__,
        )
        return _fallback_query_response(query, reason="query_failed")

    global _model_loaded, _retrieval_warmed
    _retrieval_warmed = True
    _model_loaded = True
    logger.info("Query path OK — answer_query completed; model_loaded set to True (retrieval + LLM path exercised).")
    gc.collect()
    return out


def _build_health_response() -> HealthResponse:
    mock_mode = not _has_groq_key()
    rag_available = rag_orchestrator is not None
    rag_init_degraded = not rag_available and (_degraded_no_rag or _rag_init_timed_out)
    degraded = rag_init_degraded or _last_query_pipeline_degraded
    index_on_disk = _chroma_index_on_disk()

    if rag_available:
        if _last_query_pipeline_degraded:
            msg = (
                "RAG is initialized, but the last POST /query failed (timeout, error, or degraded fallback). "
                "Check logs for answer_query / Groq / retrieval. A successful query clears this state."
            )
        else:
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

    corpus_last_updated: Optional[str] = None
    nav_as_of_max: Optional[str] = None
    try:
        freshness = build_freshness_report(BASE_DIR)
        corpus_last_updated = freshness.get("manifest_last_updated")
        nav_as_of_max = freshness.get("nav_as_of_max")
    except Exception:
        pass

    return HealthResponse(
        status="healthy",
        ready=True,
        rag_available=rag_available,
        rag_ready=_retrieval_warmed,
        message=msg,
        schemes_loaded=len(_schemes),
        memory_mb=_safe_memory_mb(),
        model_loaded=_model_loaded,
        chroma_loaded=_chroma_loaded,
        mock_mode=mock_mode,
        degraded=degraded,
        index_on_disk=index_on_disk,
        api_version=APP_VERSION,
        last_query_status=_last_query_status_report,
        corpus_last_updated=corpus_last_updated,
        nav_as_of_max=nav_as_of_max,
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
            api_version=APP_VERSION,
            last_query_status=None,
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
    _log_index_diagnostics()
    try:
        await asyncio.to_thread(_sync_chroma_sqlite_probe)
    except Exception:
        logger.exception("STARTUP_CHROMA_PROBE thread wrapper failed")
    try:
        _schemes = _load_schemes_only()
    except Exception:
        logger.exception("Scheme load failed; continuing with empty schemes")
        _schemes = []

    mem = _memory_mb()
    logger.info(
        "Startup complete — routes live | pid=%s | schemes=%s RAM=%.1f MB | "
        "mock_mode on /health = not groq_key_present.",
        os.getpid(),
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
    version=APP_VERSION,
    lifespan=lifespan,
)

_configure_cors(app)


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

    logger.info(
        "POST /query — RAG lazy init + answer (single wall timeout ~%.0fs; QUERY_TIMEOUT_SECONDS=%.0fs advisory)",
        combined_ceiling,
        query_timeout_s,
    )

    try:
        async with asyncio.timeout(combined_ceiling):
            await ensure_rag_engine_async(request)
            response = await asyncio.to_thread(_run_query_sync, q)
        st = response.get("status", "error")
        raw_sources = response.get("sources") or []
        sources: List[SourceRef] = []
        for s in raw_sources:
            if isinstance(s, dict) and s.get("url"):
                sources.append(
                    SourceRef(
                        title=str(s.get("title") or s.get("scheme_name") or "Source"),
                        url=str(s["url"]),
                        scheme_name=s.get("scheme_name"),
                        nav_as_of=s.get("nav_as_of"),
                    )
                )
        out = QueryResponse(
            answer=response.get("answer", "") or "No answer returned.",
            source=response.get("source"),
            source_link=response.get("source_link"),
            last_updated=response.get("last_updated"),
            sources=sources,
            status=st if isinstance(st, str) else "error",
        )
        _record_last_query_status(out.status)
        return out
    except TimeoutError:
        logger.warning("POST /query timed out (combined init+answer ceiling ~%.0fs)", combined_ceiling)
        fb = _fallback_query_response(q, reason="query_timeout")
        _record_last_query_status("timeout")
        return QueryResponse(answer=fb["answer"], status="timeout")
    except Exception:
        logger.exception("Query failed")
        fb = _fallback_query_response(q, reason="query_failed")
        _record_last_query_status("error")
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
