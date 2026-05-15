import sys
import os
import logging
import re
import time
import traceback
from typing import Dict, Any, Optional, List

_MAX_MULTI_SCHEME_SEARCHES = max(1, min(int(os.getenv("QUERY_MAX_SCHEME_SEARCHES", "4")), 8))
_PER_SCHEME_RESULTS = max(1, min(int(os.getenv("QUERY_PER_SCHEME_RESULTS", "2")), 5))
_GENERAL_RESULTS = max(3, min(int(os.getenv("QUERY_GENERAL_RESULTS", "5")), 10))

# Add Phase 2 and Phase 3 src to path
BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(BASE, 'phase2_retrieval_layer', 'src'))
sys.path.insert(0, os.path.join(BASE, 'phase3_reasoning_guardrails', 'src'))

from query_processor import QueryProcessor
from retriever import HybridRetriever
from context_builder import ContextBuilder
from answer_sanitizer import sanitize_answer_text, resolve_source_fields
from llm_client import MockLLM, classify_llm_failure, _groq_api_key
from extractive_fallback import (
    build_compact_llm_context,
    build_extractive_answer,
    _group_by_scheme,
    _merge_facts,
)

logger = logging.getLogger(__name__)

class RAGOrchestrator:
    """Orchestrates the full RAG pipeline."""

    def __init__(
        self,
        persist_directory: str,
        scheme_names: list,
        use_bm25: bool = False,
        use_reranker: bool = False,
        vector_fetch_k: int = 12,
    ):
        self.qp = QueryProcessor(scheme_names)
        self.retriever = HybridRetriever(
            persist_directory=persist_directory,
            collection_name="mf_faq_corpus",
            use_bm25=use_bm25,
            use_reranker=use_reranker,
            vector_fetch_k=vector_fetch_k,
        )
        self.builder = ContextBuilder()
        self._generator = None

    def warm_retrieval_stack(self, probe_query: str = "HDFC mutual fund overview") -> None:
        """Embedding model + one vector search — no LLM call."""
        self.retriever.warm_vector_pipeline(probe_query)

    def _get_generator(self):
        """Lazy LLM + AnswerGenerator so startup stays lightweight."""
        import gc
        from answer_generator import AnswerGenerator
        from llm_client import get_llm_provider, _groq_api_key

        if self._generator is None:
            self._generator = AnswerGenerator(get_llm_provider())
            gc.collect()
            return self._generator

        if isinstance(self._generator.llm, MockLLM) and _groq_api_key():
            logger.warning(
                "Recreating AnswerGenerator — GROQ_API_KEY is now set (was MockLLM)."
            )
            self._generator = AnswerGenerator(get_llm_provider())
            gc.collect()
        return self._generator

    def _safe_search(
        self,
        query: str,
        n_results: int,
        filters,
        label: str,
    ):
        """Chroma/embedding failures must not take down the whole answer path."""
        try:
            return self.retriever.search(
                query=query,
                n_results=n_results,
                filters=filters,
            )
        except Exception:
            logger.exception("Retriever.search failed (%s)", label)
            return []

    @staticmethod
    def _minimal_context(results: List[Dict[str, Any]]) -> str:
        parts: List[str] = []
        for i, res in enumerate(results[:4], 1):
            meta = res.get("metadata") if isinstance(res.get("metadata"), dict) else {}
            text = (res.get("text") or "").strip().replace("\n", " ")
            scheme = meta.get("scheme_name") or "Fund"
            if text:
                parts.append(f"[{i}] {scheme}: {text[:480]}")
        return "\n\n".join(parts) if parts else "No relevant context found."

    def _retrieval_fallback_answer(
        self,
        query: str,
        results: List[Dict[str, Any]],
        *,
        llm_reason: str = "unavailable",
        intent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Clean fact-based answer when Groq fails — no raw HTML chunk dumps."""
        extracted = build_extractive_answer(query, results, intent=intent)
        if extracted:
            if llm_reason == "auth":
                suffix = " Configure GROQ_API_KEY on Railway for AI-written summaries."
            elif llm_reason in ("timeout", "rate_limit"):
                suffix = ""
            else:
                suffix = ""
            body = extracted + suffix
            out = self._apply_policy(body, results)
            out["status"] = "success"
            logger.info(
                "answer_query: extractive fallback OK (llm_reason=%s) chars=%s",
                llm_reason,
                len(body),
            )
            return out

        lines: List[str] = []
        for scheme, chunks in _group_by_scheme(results)[:2]:
            facts = _merge_facts(chunks)
            short = scheme.replace(" Direct Growth", "")
            if facts.get("nav"):
                lines.append(f"{short}: latest NAV {facts['nav']}.")
            elif facts.get("expense_ratio"):
                lines.append(f"{short}: expense ratio {facts['expense_ratio']}.")

        if lines:
            body = " ".join(lines)
            out = self._apply_policy(body, results)
            out["status"] = "success"
            return out

        return {
            "answer": (
                "I found fund records but could not summarize them right now. "
                "Please try again in a moment or ask a more specific question (e.g. NAV or expense ratio)."
            ),
            "source": None,
            "source_link": "https://www.hdfcfund.com/",
            "last_updated": None,
            "sources": [],
            "status": "degraded",
        }

    def _log_chunk_preview(self, results: List[Dict[str, Any]], max_chars: int = 180) -> None:
        if not results:
            logger.info("chunk_preview: (no chunks)")
            return
        r0 = results[0]
        meta = r0.get("metadata") or {}
        text = (r0.get("text") or "")[:max_chars]
        logger.info(
            "chunk_preview: first id=%s scheme_name=%r text_len=%s text_preview=%r",
            r0.get("id"),
            meta.get("scheme_name"),
            len(r0.get("text") or ""),
            text,
        )

    def answer_query(self, query: str) -> Dict[str, Any]:
        """Main entry point to get an answer."""
        wall0 = time.perf_counter()
        q = (query or "").strip()
        logger.info("answer_query START query_len=%s preview=%r", len(q), q[:200])

        # --- Stage: process_query ---
        t0 = time.perf_counter()
        try:
            proc = self.qp.process_query(q)
            filters = proc["filters"]
            intent = proc["intent"]
        except Exception as e:
            logger.exception(
                "answer_query STAGE=process_query FAILED after_ms=%.1f err=%s — using general retrieval",
                (time.perf_counter() - t0) * 1000,
                type(e).__name__,
            )
            filters = {}
            intent = None

        logger.info(
            "answer_query STAGE=process_query OK ms=%.1f filters=%s intent=%s",
            (time.perf_counter() - t0) * 1000,
            filters,
            intent,
        )

        # --- Stage: retrieval ---
        t0 = time.perf_counter()
        all_results: List[Dict[str, Any]] = []
        is_multi = False

        try:
            if filters and "scheme_name" in filters:
                scheme_filter = filters["scheme_name"]
                if isinstance(scheme_filter, dict) and "$in" in scheme_filter:
                    is_multi = True
                    schemes = list(scheme_filter["$in"])[:_MAX_MULTI_SCHEME_SEARCHES]
                    if len(scheme_filter["$in"]) > len(schemes):
                        logger.warning(
                            "Multi-fund retrieval capped %s -> %s schemes (QUERY_MAX_SCHEME_SEARCHES)",
                            len(scheme_filter["$in"]),
                            len(schemes),
                        )
                    logger.info(
                        "Retrieval mode=multi-fund schemes_count=%s per_scheme_k=%s",
                        len(schemes),
                        _PER_SCHEME_RESULTS,
                    )

                    for scheme in schemes:
                        scheme_results = self._safe_search(
                            q,
                            _PER_SCHEME_RESULTS,
                            {"scheme_name": scheme},
                            f"multi-fund:{str(scheme)[:48]}",
                        )
                        all_results.extend(scheme_results)
                else:
                    logger.info("Retrieval mode=single-fund scheme=%r", scheme_filter)
                    all_results = self._safe_search(q, _PER_SCHEME_RESULTS + 1, filters, "single-fund")
            else:
                logger.info("Retrieval mode=general (no scheme filter)")
                all_results = self._safe_search(q, _GENERAL_RESULTS, None, "general")
        except Exception as e:
            logger.exception(
                "answer_query STAGE=retrieval FAILED after_ms=%.1f err=%s — recovery general search",
                (time.perf_counter() - t0) * 1000,
                type(e).__name__,
            )
            all_results = self._safe_search(q, _GENERAL_RESULTS, None, "recovery-general")

        logger.info(
            "answer_query STAGE=retrieval OK ms=%.1f chunk_count=%s intent=%s",
            (time.perf_counter() - t0) * 1000,
            len(all_results),
            intent,
        )
        self._log_chunk_preview(all_results)

        if not all_results and filters:
            logger.warning(
                "No chunks with scheme filters %s — falling back to general vector search",
                filters,
            )
            t_fb = time.perf_counter()
            all_results = self._safe_search(
                q, min(_GENERAL_RESULTS + 2, 8), None, "general-fallback-after-empty-filters"
            )
            logger.info(
                "answer_query STAGE=retrieval_fallback ms=%.1f chunk_count=%s",
                (time.perf_counter() - t_fb) * 1000,
                len(all_results),
            )
            self._log_chunk_preview(all_results)

        if not all_results:
            logger.info(
                "answer_query END status=no_results total_ms=%.1f",
                (time.perf_counter() - wall0) * 1000,
            )
            return {
                "answer": "I'm sorry, I couldn't find any information about that in my records.",
                "source": None,
                "status": "no_results",
            }

        # --- Stage: build_context ---
        t0 = time.perf_counter()
        try:
            context = self.builder.build_context(all_results, intent=intent)
        except Exception as e:
            logger.exception(
                "answer_query STAGE=build_context FAILED after_ms=%.1f err=%s chunks=%s — minimal context",
                (time.perf_counter() - t0) * 1000,
                type(e).__name__,
                len(all_results),
            )
            context = self._minimal_context(all_results)

        ctx_len = len(context or "")
        logger.info(
            "answer_query STAGE=build_context OK ms=%.1f context_chars=%s multi_fund=%s",
            (time.perf_counter() - t0) * 1000,
            ctx_len,
            is_multi,
        )
        if ctx_len == 0 or (context or "").strip() == "No relevant context found.":
            logger.warning("answer_query: context empty or placeholder despite chunk_count=%s", len(all_results))

        # --- Stage: llm_generate ---
        compact_ctx = build_compact_llm_context(all_results, intent=intent, query=q)
        ctx_for_llm = compact_ctx if len(compact_ctx) > 80 else context
        logger.info(
            "answer_query STAGE=llm_context compact_chars=%s full_chars=%s using=%s",
            len(compact_ctx),
            ctx_len,
            "compact" if ctx_for_llm == compact_ctx else "full",
        )

        t0 = time.perf_counter()
        raw_answer: str = ""
        if _groq_api_key():
            self._generator = None
        try:
            raw_answer = self._get_generator().generate_answer(
                q, ctx_for_llm, multi_fund=is_multi
            )
        except Exception as e:
            cat, code = classify_llm_failure(e)
            logger.error(
                "answer_query STAGE=llm_generate FAILED after_ms=%.1f category=%s http_status=%s "
                "err_type=%s context_chars=%s — extractive fallback",
                (time.perf_counter() - t0) * 1000,
                cat,
                code,
                type(e).__name__,
                len(ctx_for_llm),
            )
            return self._retrieval_fallback_answer(
                q, all_results, llm_reason=cat, intent=intent
            )

        if not isinstance(raw_answer, str):
            logger.warning("answer_query STAGE=llm_generate non-string answer — extractive fallback")
            return self._retrieval_fallback_answer(
                q, all_results, llm_reason="empty_response", intent=intent
            )

        if not raw_answer.strip():
            logger.warning("answer_query STAGE=llm_generate empty string — extractive fallback")
            return self._retrieval_fallback_answer(
                q, all_results, llm_reason="empty_response", intent=intent
            )

        ans_preview = raw_answer[:200]
        logger.info(
            "answer_query STAGE=llm_generate OK ms=%.1f answer_preview=%r",
            (time.perf_counter() - t0) * 1000,
            ans_preview,
        )

        # --- Stage: apply_policy ---
        t0 = time.perf_counter()
        try:
            final_response = self._apply_policy(raw_answer, all_results)
        except Exception as e:
            logger.exception(
                "answer_query STAGE=apply_policy FAILED after_ms=%.1f err=%s — retrieval fallback",
                (time.perf_counter() - t0) * 1000,
                type(e).__name__,
            )
            return self._retrieval_fallback_answer(
                q, all_results, llm_reason="policy_error", intent=intent
            )

        logger.info(
            "answer_query STAGE=apply_policy OK ms=%.1f final_status=%s total_ms=%.1f",
            (time.perf_counter() - t0) * 1000,
            final_response.get("status"),
            (time.perf_counter() - wall0) * 1000,
        )
        return final_response

    def _apply_policy(self, answer: str, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Ensures the response follows the URL and sentence constraints."""
        if not isinstance(answer, str) or answer is None:
            logger.warning("_apply_policy: LLM returned non-string answer — coercing to empty")
            answer = ""

        # Check if "don't know" or similar is in answer
        refusal_keywords = ["don't know", "do not have enough information", "not found", "cannot answer"]
        is_refusal = any(kw in answer.lower() for kw in refusal_keywords)

        clean_answer = sanitize_answer_text(answer)

        try:
            src = resolve_source_fields(results)
        except Exception:
            logger.exception("_apply_policy: resolve_source_fields failed — using defaults")
            src = {
                "source": None,
                "source_link": "https://www.hdfcfund.com/",
                "last_updated": None,
                "sources": [],
            }
        source_info = src.get("source")
        source_link = src.get("source_link")
        last_updated = src.get("last_updated")
        sources = src.get("sources") or []

        if is_refusal:
            return {
                "answer": clean_answer,
                "source": None,
                "source_link": None,
                "last_updated": None,
                "sources": [],
                "status": "refusal",
            }

        # Ensure sentence count (crude split) - allow 4 for multi-fund
        sentences = re.split(r'(?<=[.!?])\s+', clean_answer.strip())
        if len(sentences) > 4:
            clean_answer = " ".join(sentences[:4])

        return {
            "answer": clean_answer,
            "source": source_info,
            "source_link": source_link,
            "last_updated": last_updated,
            "sources": sources,
            "status": "success",
        }

if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.INFO)
    # Mock scheme names
    schemes = ["HDFC Flexi Cap Fund", "HDFC Balanced Advantage Fund"]
    orch = RAGOrchestrator(persist_directory="data/indexed", scheme_names=schemes)
    
    print(orch.answer_query("What is the exit load for HDFC Flexi Cap?"))
    print("-" * 20)
    print(orch.answer_query("Should I buy HDFC Flexi Cap?"))
