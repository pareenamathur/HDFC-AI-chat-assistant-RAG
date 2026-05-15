import logging
import time
from typing import List, Dict, Any, Optional
from llm_client import LLMProvider

logger = logging.getLogger(__name__)

class AnswerGenerator:
    """Handles the generation of factual answers using Groq/LLM."""

    def __init__(self, llm_provider: LLMProvider):
        self.llm = llm_provider

    def generate_answer(self, query: str, context: str, multi_fund: bool = False) -> str:
        """
        Generates a compliant, factual answer based on context.
        
        Args:
            query: The user's question.
            context: The retrieved factual context.
            multi_fund: Whether multiple funds are being discussed.
        """
        system_prompt = self._get_system_prompt(multi_fund)
        user_prompt = f"Context:\n{context}\n\nQuestion: {query}"

        ctx_n = len(context or "")
        logger.info(
            "AnswerGenerator: LLM call starting context_chars=%s multi_fund=%s",
            ctx_n,
            multi_fund,
        )
        t0 = time.perf_counter()
        out = self.llm.generate(system_prompt, user_prompt)
        logger.info(
            "AnswerGenerator: LLM call finished ms=%.1f answer_chars=%s",
            (time.perf_counter() - t0) * 1000,
            len(out or ""),
        )
        return out

    def _get_system_prompt(self, multi_fund: bool = False) -> str:
        """Returns the strict system instructions for the LLM."""
        link_constraint = "Exactly one official source link at the end."
        if multi_fund:
            link_constraint = "Provide the official source link for each fund discussed at the end."

        return (
            "You are a Mutual Fund FAQ Assistant for HDFC Mutual Fund.\n"
            "Answer ONLY using the provided context. If multiple sources conflict, prioritize the one with the most recent date.\n"
            "STRICT CONSTRAINTS:\n"
            "1. Maximum 3-4 sentences total (be extremely concise even for multiple funds).\n"
            f"2. {link_constraint} Use the **Official citation URL** from each [Source] line when present (https://www.hdfcfund.com/); "
            "if the line also shows local_snapshot_file=…, that is only the offline scrape filename — still cite the https URL exactly.\n"
            "3. If you don't know the answer for a specific fund, do NOT provide a URL for it.\n"
            "4. Do NOT include any personal information.\n"
            "5. NO investment advice or recommendations.\n"
            "6. Always provide the most up-to-date figures found in the context."
        )
