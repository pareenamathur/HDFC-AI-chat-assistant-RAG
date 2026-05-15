import logging
import os
import time
from typing import List, Dict, Any, Optional
from llm_client import LLMProvider, LLMError, classify_llm_failure

logger = logging.getLogger(__name__)

class AnswerGenerator:
    """Handles the generation of factual answers using Groq/LLM."""

    def __init__(self, llm_provider: LLMProvider):
        self.llm = llm_provider
        provider_name = type(llm_provider).__name__
        model = getattr(llm_provider, "model", None)
        logger.info(
            "AnswerGenerator init provider=%s model=%s",
            provider_name,
            model or "(n/a)",
        )

    def generate_answer(self, query: str, context: str, multi_fund: bool = False) -> str:
        """
        Generates a compliant, factual answer based on context.
        
        Args:
            query: The user's question.
            context: The retrieved factual context.
            multi_fund: Whether multiple funds are being discussed.
        """
        system_prompt = self._get_system_prompt(multi_fund)
        max_ctx = int(os.getenv("LLM_MAX_CONTEXT_CHARS", "8000"))
        ctx = (context or "").strip()
        if len(ctx) > max_ctx:
            logger.warning(
                "AnswerGenerator: truncating context %s -> %s chars",
                len(ctx),
                max_ctx,
            )
            ctx = ctx[:max_ctx] + "\n\n[Context truncated for latency.]"
        user_prompt = f"Context:\n{ctx}\n\nQuestion: {query}"

        ctx_n = len(ctx)
        logger.info(
            "AnswerGenerator: LLM call starting provider=%s context_chars=%s query_chars=%s multi_fund=%s",
            type(self.llm).__name__,
            ctx_n,
            len((query or "").strip()),
            multi_fund,
        )
        t0 = time.perf_counter()
        try:
            out = self.llm.generate(system_prompt, user_prompt)
        except Exception as e:
            cat, code = classify_llm_failure(e)
            logger.error(
                "AnswerGenerator: LLM call FAILED ms=%.1f category=%s http_status=%s err_type=%s",
                (time.perf_counter() - t0) * 1000,
                cat,
                code,
                type(e).__name__,
            )
            if isinstance(e, LLMError):
                raise
            raise LLMError(
                f"LLM generate failed ({cat}): {str(e)[:300]}",
                category=cat,
                status_code=code,
            ) from e
        logger.info(
            "AnswerGenerator: LLM call finished ms=%.1f answer_chars=%s preview=%r",
            (time.perf_counter() - t0) * 1000,
            len(out or ""),
            (out or "")[:160],
        )
        return out

    def _get_system_prompt(self, multi_fund: bool = False) -> str:
        """Returns the strict system instructions for the LLM."""
        return (
            "You are a Mutual Fund FAQ Assistant for HDFC Mutual Fund.\n"
            "Answer ONLY using the provided context. If multiple sources conflict, prioritize the one with the most recent date.\n"
            "STRICT CONSTRAINTS:\n"
            "1. Maximum 3-4 sentences total (be extremely concise even for multiple funds).\n"
            "2. Do NOT include URLs, [Source] tags, footnotes, or disclaimers about missing links — "
            "the application shows the official HDFC link separately.\n"
            "3. When context shows 'NAV: DD Mon YY', treat that as the data-as-of date for figures.\n"
            "4. Do NOT include any personal information.\n"
            "5. NO investment advice or recommendations.\n"
            "6. Always use the most up-to-date figures found in the context."
        )
