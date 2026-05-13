"""
HDFC Mutual Fund Assistant — Streamlit Cloud production build.

Memory profile: lazy-loaded embedding + LLM, BM25/rerank off, CPU-only torch.
UI: dark theme, Groww/HDFC-inspired hierarchy (reference: stitch_groww_hdfc_ai_assistant).
"""

from __future__ import annotations

import gc
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional

# Thread caps before importing numeric stacks (torch / transformers)
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("CHROMA_TELEMETRY", "false")

# Optional protobuf runtime override (Streamlit Secrets). Prefer requirements pins.
_pb_impl = os.getenv("STREAMLIT_PROTOBUF_PYTHON_IMPL", "").strip().lower()
if _pb_impl in ("python", "cpp", "upb"):
    os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = _pb_impl

# Streamlit must load before @st.cache_* decorators are evaluated (not deferred).
import streamlit as st

BASE = os.path.dirname(os.path.abspath(__file__))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _ensure_phase_paths() -> None:
    """Insert RAG src paths only when needed — keeps module import free of phase imports."""
    p2 = os.path.join(BASE, "phase2_retrieval_layer", "src")
    p3 = os.path.join(BASE, "phase3_reasoning_guardrails", "src")
    if p2 not in sys.path:
        sys.path.insert(0, p2)
    if p3 not in sys.path:
        sys.path.insert(0, p3)

# --- Sentinel when RAG stack fails ---
class _OrchestratorUnavailable:
    __slots__ = ("reason",)

    def __init__(self, reason: str) -> None:
        self.reason = reason


USE_BM25 = os.getenv("USE_BM25", "false").lower() in ("1", "true", "yes")
USE_RERANKER = os.getenv("USE_RERANKER", "false").lower() in ("1", "true", "yes")


def _vector_fetch_k() -> int:
    try:
        return int(os.getenv("STREAMLIT_VECTOR_FETCH_K", "12"))
    except ValueError:
        return 12

SUGGESTED_PROMPTS = [
    "What is the expense ratio of HDFC Balanced Advantage Fund?",
    "What is the exit load for HDFC Flexi Cap Fund?",
    "How do SIPs work for HDFC mutual funds?",
]


def _minimal_dark_css() -> None:
    """Tie Streamlit widgets to our dark palette; keep surface/card readable."""
    st.markdown(
        """
        <style>
          /* Canvas depth (config.toml sets theme; this reinforces app chrome) */
          .stApp { background-color: #0B0F14; }
          section[data-testid="stSidebar"] {
            background-color: #0B0F14 !important;
            border-right: 1px solid rgba(148, 163, 184, 0.18);
          }
          .block-container {
            padding-top: 1.5rem;
            padding-bottom: 2rem;
            max-width: 960px;
          }
          /* Inputs: visible borders on dark */
          .stTextInput input, div[data-baseweb="textarea"] textarea {
            border: 1px solid rgba(148, 163, 184, 0.35) !important;
            border-radius: 10px !important;
            background-color: #111827 !important;
            color: #E5E7EB !important;
          }
          /* Primary buttons: teal accent + readable label */
          .stButton > button[kind="primary"] {
            background-color: #4ECDC4 !important;
            color: #0B0F14 !important;
            font-weight: 600 !important;
            border-radius: 10px !important;
            border: none !important;
          }
          .stButton > button[kind="secondary"] {
            border: 1px solid rgba(148, 163, 184, 0.45) !important;
            color: #E5E7EB !important;
            background-color: #111827 !important;
            border-radius: 10px !important;
          }
          /* Tabs: clearer separation */
          .stTabs [data-baseweb="tab-list"] {
            gap: 0.5rem;
            border-bottom: 1px solid rgba(148, 163, 184, 0.2);
          }
          .stTabs [data-baseweb="tab"] {
            border-radius: 8px 8px 0 0;
          }
          /* Alerts inherit Streamlit dark styling; bump contrast slightly */
          div[data-testid="stAlert"] {
            border-radius: 10px;
          }
          /* Chat */
          .stChatMessage {
            border-radius: 12px;
            border: 1px solid rgba(148, 163, 184, 0.15);
          }
          footer { visibility: hidden; }
          @media (max-width: 768px) {
            .block-container { padding-left: 1rem !important; padding-right: 1rem !important; }
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _memory_mb() -> Optional[float]:
    try:
        import psutil
        return psutil.Process().memory_info().rss / 1024 / 1024
    except Exception:
        return None


@st.cache_data(show_spinner=False, max_entries=1)
def _load_scheme_names() -> List[str]:
    processed = os.getenv("PROCESSED_DATA_PATH", os.path.join(BASE, "data", "processed"))
    path = os.path.join(processed, "chunked_data_phase1.4.json")
    if not os.path.exists(path):
        logger.warning("Missing chunked data: %s", path)
        return []
    with open(path, "r", encoding="utf-8") as f:
        chunks = json.load(f)
    return sorted({c["scheme_name"] for c in chunks})


@st.cache_resource(show_spinner="Loading assistant engine…")
def _get_orchestrator() -> Any:
    """Lazy ML/RAG load only here — never at module import time."""
    try:
        _ensure_phase_paths()
        from orchestrator import RAGOrchestrator

        indexed = os.getenv("INDEXED_DATA_PATH", os.path.join(BASE, "data", "indexed"))
        schemes = _load_scheme_names()
        gc.collect()
        return RAGOrchestrator(
            persist_directory=indexed,
            scheme_names=schemes,
            use_bm25=USE_BM25,
            use_reranker=USE_RERANKER,
            vector_fetch_k=_vector_fetch_k(),
        )
    except Exception as e:
        logger.exception("RAG orchestrator initialization failed")
        return _OrchestratorUnavailable(str(e))


def _friendly_copy(status: str, raw: str) -> str:
    """Short, non-technical messages for end users."""
    if status == "ai_unavailable":
        return (
            "The assistant couldn’t start fully right now. "
            "Please wait a moment and try again, or refresh the page."
        )
    if status == "error":
        return "Something went wrong on our side. Please try your question again in a few seconds."
    if status in ("no_results", "refusal"):
        return raw
    return raw


def _render_dashboard_header() -> None:
    c1, c2 = st.columns([3, 1])
    with c1:
        st.markdown("## HDFC Mutual Fund Assistant")
        st.caption(
            "Ask plain-language questions about HDFC schemes. Answers use your indexed fund facts—not personal advice."
        )
    with c2:
        mb = _memory_mb()
        if mb is not None:
            st.metric("Memory (approx.)", f"{mb:.0f} MB")


def _sidebar_nav() -> str:
    with st.sidebar:
        st.markdown("### HDFC Assistant")
        st.caption("Navigation")
        page = st.radio(
            "Section",
            ["Search", "Chat", "Schemes"],
            label_visibility="collapsed",
            key="nav_page",
        )
        st.divider()
        st.markdown("**Tips**")
        st.markdown(
            "- Use **Search** for one-off factual questions.\n"
            "- Use **Chat** for a back-and-forth thread.\n"
            "- **Schemes** lists names from your data file."
        )
        st.divider()
        st.caption(
            "Questions about investments are answered from documents only. "
            "Not investment advice."
        )
    return page


def _format_answer_block(response: Dict[str, Any]) -> None:
    status = response.get("status", "error")
    text = response.get("answer", "") or "No answer returned."
    if status == "ai_unavailable":
        st.warning(_friendly_copy("ai_unavailable", text))
        detail = response.get("detail")
        if detail:
            with st.expander("Details (for support)"):
                st.code(str(detail), language="text")
        return
    if status == "success":
        st.success(text)
        meta_parts = []
        if response.get("source"):
            meta_parts.append(f"**Source:** {response['source']}")
        if response.get("last_updated"):
            meta_parts.append(f"**As of:** {response['last_updated']}")
        if meta_parts:
            st.info("\n\n".join(meta_parts))
    elif status in ("no_results", "refusal"):
        st.info(text)
    else:
        st.error(_friendly_copy("error", text))


def run_query(query: str) -> Dict[str, Any]:
    q = (query or "").strip()
    if not q:
        return {"answer": "Please type a question first.", "status": "error"}
    try:
        orch = _get_orchestrator()
        if isinstance(orch, _OrchestratorUnavailable):
            st.session_state["_ai_engine_failed"] = True
            return {
                "answer": _friendly_copy("ai_unavailable", ""),
                "status": "ai_unavailable",
                "detail": orch.reason,
            }
        with st.spinner("Looking up relevant fund information…"):
            out = orch.answer_query(q)
        gc.collect()
        return out
    except Exception:
        logger.exception("Query failed")
        return {
            "answer": _friendly_copy("error", ""),
            "status": "error",
        }


def _panel_search() -> None:
    st.subheader("Search")
    st.caption("One question at a time—best for NAV, loads, ratios, and scheme facts.")

    # Suggestion buttons cannot assign to `search_q` after `st.text_input(key="search_q")`
    # in the same run — Streamlit raises StreamlitAPIException. Store pending text, rerun,
    # then apply it here before the widget is created.
    if "_search_suggestion_pending" in st.session_state:
        st.session_state["search_q"] = st.session_state.pop("_search_suggestion_pending")

    with st.container(border=True):
        q = st.text_input(
            "Your question",
            placeholder="e.g. What is the exit load for HDFC Flexi Cap Fund?",
            key="search_q",
            label_visibility="visible",
        )
        go = st.button("Search", type="primary", use_container_width=True)

        st.markdown("**Try asking**")
        cols = st.columns(len(SUGGESTED_PROMPTS))
        for i, suggestion in enumerate(SUGGESTED_PROMPTS):
            short = suggestion if len(suggestion) <= 52 else suggestion[:49] + "…"
            if cols[i].button(short, key=f"sug_{i}", use_container_width=True):
                st.session_state["_search_suggestion_pending"] = suggestion
                st.rerun()

    if go and q.strip():
        res = run_query(q)
        st.markdown("---")
        with st.container(border=True):
            st.markdown("#### Answer")
            _format_answer_block(res)
    elif go and not q.strip():
        st.info("Enter a question above, then tap **Search**.")


def _panel_chat() -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = []

    st.subheader("Chat")
    st.caption("Same answers as Search—organized as a conversation.")

    chat_area = st.container(border=True)
    with chat_area:
        if not st.session_state.messages:
            st.markdown("##### Start the conversation")
            st.info(
                "Ask anything about HDFC mutual funds from your indexed documents. "
                "Responses are factual summaries, not recommendations."
            )
            st.markdown("**Suggested starters**")
            for idx, sp in enumerate(SUGGESTED_PROMPTS):
                if st.button(sp, key=f"chatstarter_{idx}", use_container_width=True):
                    st.session_state["_pending_chat"] = sp
        else:
            for m in st.session_state.messages:
                with st.chat_message(m["role"]):
                    st.markdown(m["content"])

    pending = st.session_state.pop("_pending_chat", None)
    chat_raw = st.chat_input("Message about HDFC mutual funds…")
    if pending and str(pending).strip():
        prompt = str(pending).strip()
    elif chat_raw and str(chat_raw).strip():
        prompt = str(chat_raw).strip()
    else:
        prompt = ""

    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        res = run_query(prompt)
        status = res.get("status", "error")
        reply = res.get("answer", "") or ""
        if status == "success" and res.get("source"):
            reply += f"\n\n**Source:** {res['source']}"
        elif status in ("no_results", "refusal"):
            reply = reply
        elif status == "ai_unavailable":
            reply = _friendly_copy("ai_unavailable", reply)
        elif status == "error":
            reply = _friendly_copy("error", reply)
        st.session_state.messages.append({"role": "assistant", "content": reply})
        gc.collect()
        st.rerun()


def _panel_schemes() -> None:
    schemes = _load_scheme_names()
    st.subheader("Schemes in your corpus")
    st.caption("Names detected from your processed chunk file.")

    filter_q = st.text_input("Filter schemes", placeholder="Type to filter…", key="scheme_filter")

    with st.container(border=True):
        if not schemes:
            st.warning(
                "No scheme list found. Add `data/processed/chunked_data_phase1.4.json` "
                "to this deployment."
            )
            return

        filtered = schemes
        if filter_q.strip():
            fq = filter_q.strip().lower()
            filtered = [s for s in schemes if fq in s.lower()]

        if not filtered:
            st.info("No schemes match that filter. Clear the filter to see all.")
            return

        st.metric("Schemes shown", len(filtered))
        cols = st.columns(3)
        for i, name in enumerate(filtered[:120]):
            cols[i % 3].markdown(f"- {name}")
        if len(filtered) > 120:
            st.caption(f"… and {len(filtered) - 120} more. Narrow your filter for easier browsing.")


def main() -> None:
    st.set_page_config(
        page_title="HDFC MF Assistant",
        page_icon="🏦",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _minimal_dark_css()

    page = _sidebar_nav()

    _render_dashboard_header()

    if st.session_state.get("_ai_engine_failed"):
        st.warning(
            "The assistant had trouble loading earlier this session. "
            "You can still browse schemes; try Search or Chat again after a short wait."
        )

    # Main dashboard: radio-driven panels (clear separation vs. tabs-in-main)
    if page == "Search":
        _panel_search()
    elif page == "Chat":
        _panel_chat()
    else:
        _panel_schemes()

    st.divider()
    st.caption(
        "Educational information only—not investment, tax, or legal advice. "
        "Consult a qualified advisor before investing."
    )


# Streamlit executes this script on every rerun; always enter the app (do not gate on __main__ —
# some runners/launchers omit __name__ == "__main__", which breaks Cloud health checks).
main()
