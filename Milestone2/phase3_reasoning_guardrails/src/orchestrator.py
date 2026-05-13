import sys
import os
import logging
import re
import time
import traceback
from typing import Dict, Any, Optional, List

# Add Phase 2 and Phase 3 src to path
BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(BASE, 'phase2_retrieval_layer', 'src'))
sys.path.insert(0, os.path.join(BASE, 'phase3_reasoning_guardrails', 'src'))

from query_processor import QueryProcessor
from retriever import HybridRetriever
from context_builder import ContextBuilder

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
        if self._generator is None:
            import gc
            from answer_generator import AnswerGenerator
            from llm_client import get_llm_provider
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
    def _log_chunk_preview(results: List[Dict[str, Any]], max_chars: int = 180) -> None:
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
                "answer_query STAGE=process_query FAILED after_ms=%.1f err=%s",
                (time.perf_counter() - t0) * 1000,
                type(e).__name__,
            )
            logger.error("answer_query STAGE=process_query traceback:\n%s", traceback.format_exc())
            raise

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
                    schemes = scheme_filter["$in"]
                    logger.info("Retrieval mode=multi-fund schemes_count=%s", len(schemes))

                    for scheme in schemes:
                        scheme_results = self._safe_search(
                            q,
                            3,
                            {"scheme_name": scheme},
                            f"multi-fund:{str(scheme)[:48]}",
                        )
                        all_results.extend(scheme_results)
                else:
                    logger.info("Retrieval mode=single-fund scheme=%r", scheme_filter)
                    all_results = self._safe_search(q, 4, filters, "single-fund")
            else:
                logger.info("Retrieval mode=general (no scheme filter)")
                all_results = self._safe_search(q, 5, None, "general")
        except Exception as e:
            logger.exception(
                "answer_query STAGE=retrieval FAILED after_ms=%.1f err=%s",
                (time.perf_counter() - t0) * 1000,
                type(e).__name__,
            )
            raise

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
            all_results = self._safe_search(q, 8, None, "general-fallback-after-empty-filters")
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
                "answer_query STAGE=build_context FAILED after_ms=%.1f err=%s chunks=%s",
                (time.perf_counter() - t0) * 1000,
                type(e).__name__,
                len(all_results),
            )
            logger.error("answer_query STAGE=build_context traceback:\n%s", traceback.format_exc())
            raise

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
        t0 = time.perf_counter()
        try:
            raw_answer = self._get_generator().generate_answer(q, context, multi_fund=is_multi)
        except Exception as e:
            logger.exception(
                "answer_query STAGE=llm_generate FAILED after_ms=%.1f err=%s context_chars=%s",
                (time.perf_counter() - t0) * 1000,
                type(e).__name__,
                ctx_len,
            )
            logger.error("answer_query STAGE=llm_generate traceback:\n%s", traceback.format_exc())
            raise

        ans_preview = (raw_answer or "")[:200] if isinstance(raw_answer, str) else repr(raw_answer)[:200]
        logger.info(
            "answer_query STAGE=llm_generate OK ms=%.1f answer_type=%s answer_preview=%r",
            (time.perf_counter() - t0) * 1000,
            type(raw_answer).__name__,
            ans_preview,
        )

        # --- Stage: apply_policy ---
        t0 = time.perf_counter()
        try:
            final_response = self._apply_policy(raw_answer, all_results)
        except Exception as e:
            logger.exception(
                "answer_query STAGE=apply_policy FAILED after_ms=%.1f err=%s",
                (time.perf_counter() - t0) * 1000,
                type(e).__name__,
            )
            logger.error("answer_query STAGE=apply_policy traceback:\n%s", traceback.format_exc())
            raise

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

        # Strip ALL URLs from the answer to prevent broken links
        clean_answer = re.sub(r'https?://\S+', '', answer).strip()
        
        # Extract source information from chunk metadata
        source_info = None
        source_link = None
        last_updated = None
        
        if results and len(results) > 0:
            # Get the top result's metadata
            top_result = results[0]
            metadata = top_result.get("metadata", {})
            if not isinstance(metadata, dict):
                metadata = {}
            
            # Extract source information
            scheme_name = metadata.get("scheme_name", "Unknown Scheme")
            source_url = metadata.get("source_url", "")
            
            # Check if source_url is a local file or a valid URL
            if source_url and not source_url.startswith("http"):
                # It's a local file, don't use it as a link
                source_info = scheme_name
                source_link = None
            elif source_url and source_url.startswith("http"):
                # It's a valid URL
                source_info = scheme_name
                source_link = source_url
            else:
                # No source URL, just use scheme name
                source_info = scheme_name
                source_link = None
            
            # Get last updated date if available
            created_at = metadata.get("created_at", "")
            if created_at:
                try:
                    # Parse the datetime and format it
                    from datetime import datetime
                    dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                    last_updated = dt.strftime("%Y-%m-%d")
                except:
                    last_updated = None
        
        # Apply user constraint: If we don't know, no source info.
        if is_refusal:
            return {
                "answer": clean_answer,
                "source": None,
                "source_link": None,
                "last_updated": None,
                "status": "refusal"
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
            "status": "success"
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
