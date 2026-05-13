import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
import logging
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)

class LLMProvider:
    """Base class for LLM providers."""
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        raise NotImplementedError

class MockLLM(LLMProvider):
    """Mock LLM for testing without API keys."""
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        logger.info("Using Mock LLM")
        # Extract the question from the prompt (it's at the end)
        question = user_prompt.split("Question:")[-1].lower() if "Question:" in user_prompt else user_prompt.lower()
        logger.info(f"MockLLM extracted question: {question}")
        
        if "expense ratio" in question:
            return "The expense ratio for this fund is 0.81%. \nSource: https://www.hdfcfund.com/factsheet"
        if "exit load" in question:
            return "The exit load is 1% if redeemed within 1 year. \nSource: https://www.hdfcfund.com/sid"
        if "should i" in question or "invest" in question:
            return "I am sorry, but I cannot provide investment advice. Please consult a financial advisor."
        if "phone number" in question or "exist" in question:
            return "I do not have enough information in the provided context to answer that. \nSource: https://www.hdfcfund.com/unknown"
        
        return "I am sorry, but I do not have enough information in the provided context."

class GroqProvider(LLMProvider):
    """Groq implementation with bounded LLM wall time (no infinite hangs)."""

    _pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="groq")

    def __init__(self, api_key: str, model: Optional[str] = None):
        from groq import Groq
        self.client = Groq(api_key=api_key)
        self.model = model or os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
        logger.info("GroqProvider model=%s (override with GROQ_MODEL)", self.model)

    def _create(self, system_prompt: str, user_prompt: str) -> str:
        sys_len = len(system_prompt or "")
        usr_len = len(user_prompt or "")
        logger.info(
            "Groq request initiated model=%s system_chars=%s user_chars=%s",
            self.model,
            sys_len,
            usr_len,
        )
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0,
            )
        except Exception as e:
            body = getattr(e, "response", None)
            if body is not None and hasattr(body, "text"):
                try:
                    logger.error("Groq API error response text (truncated): %s", (body.text or "")[:800])
                except Exception:
                    pass
            logger.exception(
                "Groq chat.completions.create failed model=%s err_type=%s",
                self.model,
                type(e).__name__,
            )
            raise

        choices = getattr(response, "choices", None) or []
        if not choices:
            logger.error("Groq returned empty choices list model=%s", self.model)
            return ""

        msg = getattr(choices[0], "message", None)
        content = getattr(msg, "content", None) if msg is not None else None
        if content is None or not isinstance(content, str):
            logger.warning(
                "Groq returned empty or non-string message content finish_reason=%s",
                getattr(choices[0], "finish_reason", None),
            )
            return ""

        logger.info(
            "Groq response received model=%s content_chars=%s finish_reason=%s",
            self.model,
            len(content),
            getattr(choices[0], "finish_reason", None),
        )
        logger.info("Groq response parsing success")
        return content

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        timeout_s = float(os.getenv("LLM_TIMEOUT_SECONDS", "60"))
        fut = self._pool.submit(self._create, system_prompt, user_prompt)
        try:
            return fut.result(timeout=timeout_s)
        except FuturesTimeout:
            logger.error("Groq call exceeded LLM_TIMEOUT_SECONDS=%s", timeout_s)
            return (
                "The answer service timed out. Please try again with a shorter question."
            )
        except Exception:
            logger.exception(
                "Groq generate failed inside thread (see nested exception from _create)"
            )
            raise

def get_llm_provider() -> LLMProvider:
    """
    Groq when GROQ_API_KEY is set; otherwise MockLLM (safe for boot without secrets).
    """
    groq_api_key = os.getenv("GROQ_API_KEY")

    if groq_api_key:
        logger.info("Using GroqProvider.")
        return GroqProvider(groq_api_key)
    logger.warning(
        "No GROQ_API_KEY — using MockLLM. Set GROQ_API_KEY on Railway for live answers."
    )
    return MockLLM()
