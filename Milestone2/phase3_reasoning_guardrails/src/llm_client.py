import os
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
import logging
from typing import List, Optional, Tuple
from dotenv import load_dotenv

# Load environment variables from .env file (does not override Railway-injected env).
load_dotenv()

logger = logging.getLogger(__name__)

_DEFAULT_GROQ_MODEL = "llama-3.1-8b-instant"
_DEFAULT_FALLBACK_MODELS = (
    "llama-3.1-8b-instant",
    "llama-3.3-70b-versatile",
    "llama-3.3-8b-instant",
)


class LLMError(Exception):
    """LLM call failed after retries or returned unusable output."""

    def __init__(self, message: str, *, category: str = "unknown", status_code: Optional[int] = None):
        super().__init__(message)
        self.category = category
        self.status_code = status_code


class LLMTimeoutError(LLMError):
    """LLM call exceeded LLM_TIMEOUT_SECONDS."""

    def __init__(self, message: str, *, timeout_seconds: float):
        super().__init__(message, category="timeout")
        self.timeout_seconds = timeout_seconds


def _groq_api_key() -> str:
    return (os.getenv("GROQ_API_KEY") or "").strip()


def _openai_api_key() -> str:
    return (os.getenv("OPENAI_API_KEY") or "").strip()


def _groq_key_diagnostics() -> str:
    key = _groq_api_key()
    if not key:
        return "missing"
    prefix = key[:4] if len(key) >= 4 else "?"
    return f"present len={len(key)} prefix={prefix}…"


def _parse_fallback_models() -> List[str]:
    raw = (os.getenv("GROQ_MODEL_FALLBACKS") or "").strip()
    if raw:
        models = [m.strip() for m in raw.split(",") if m.strip()]
    else:
        models = list(_DEFAULT_FALLBACK_MODELS)
    primary = (os.getenv("GROQ_MODEL") or _DEFAULT_GROQ_MODEL).strip()
    if primary and primary not in models:
        models.insert(0, primary)
    seen: List[str] = []
    for m in models:
        if m not in seen:
            seen.append(m)
    return seen


def _extract_http_status(exc: BaseException) -> Optional[int]:
    code = getattr(exc, "status_code", None)
    if isinstance(code, int):
        return code
    resp = getattr(exc, "response", None)
    if resp is not None:
        sc = getattr(resp, "status_code", None)
        if isinstance(sc, int):
            return sc
    return None


def classify_llm_failure(exc: BaseException) -> Tuple[str, Optional[int]]:
    """Return (category, http_status) for logging and orchestrator decisions."""
    if isinstance(exc, LLMTimeoutError):
        return "timeout", getattr(exc, "status_code", None)
    if isinstance(exc, LLMError):
        return getattr(exc, "category", "llm_error"), getattr(exc, "status_code", None)

    code = _extract_http_status(exc)
    name = type(exc).__name__.lower()
    msg = str(exc).lower()

    if "api key" in msg or "invalid api key" in msg or "authentication" in msg or code == 401:
        return "auth", code
    if "model" in msg and ("not found" in msg or "decommission" in msg or "does not exist" in msg):
        return "model_not_found", code
    if ("rate" in msg and "limit" in msg) or code == 429 or "ratelimit" in name:
        return "rate_limit", code
    if "timeout" in msg or "timed out" in msg or isinstance(exc, FuturesTimeout):
        return "timeout", code
    if code in (400, 422):
        return "bad_request", code
    if code in (500, 502, 503, 504):
        return "server_error", code
    if name in ("apiconnectionerror", "connecterror", "connectionerror"):
        return "connection", code
    return "unknown", code


def _is_retryable_groq_error(exc: BaseException) -> bool:
    cat, code = classify_llm_failure(exc)
    if cat in ("rate_limit", "timeout", "server_error", "connection"):
        return True
    if code in (429, 500, 502, 503, 504):
        return True
    return False


def _is_model_not_found_error(exc: BaseException) -> bool:
    cat, _ = classify_llm_failure(exc)
    return cat == "model_not_found"


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
        models = _parse_fallback_models()
        self.model = (model or models[0] if models else _DEFAULT_GROQ_MODEL).strip()
        self._model_candidates = models or [self.model]
        self._max_tokens = max(64, min(int(os.getenv("LLM_MAX_TOKENS", "512")), 2048))
        logger.info(
            "GroqProvider init model=%s fallbacks=%s max_tokens=%s key=%s",
            self.model,
            self._model_candidates,
            self._max_tokens,
            _groq_key_diagnostics(),
        )

    def _create_with_model(self, model: str, system_prompt: str, user_prompt: str) -> str:
        sys_len = len(system_prompt or "")
        usr_len = len(user_prompt or "")
        logger.info(
            "Groq request model=%s system_chars=%s user_chars=%s max_tokens=%s",
            model,
            sys_len,
            usr_len,
            self._max_tokens,
        )
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0,
                max_tokens=self._max_tokens,
            )
        except Exception as e:
            cat, code = classify_llm_failure(e)
            body = getattr(e, "response", None)
            body_text = ""
            if body is not None:
                try:
                    body_text = (getattr(body, "text", None) or str(body))[:800]
                except Exception:
                    body_text = ""
            logger.error(
                "Groq API error model=%s category=%s status=%s err_type=%s body=%s",
                model,
                cat,
                code,
                type(e).__name__,
                body_text,
            )
            raise LLMError(
                f"Groq API failed ({cat}): {str(e)[:300]}",
                category=cat,
                status_code=code,
            ) from e

        usage = getattr(response, "usage", None)
        if usage is not None:
            logger.info(
                "Groq usage model=%s prompt_tokens=%s completion_tokens=%s total=%s",
                model,
                getattr(usage, "prompt_tokens", None),
                getattr(usage, "completion_tokens", None),
                getattr(usage, "total_tokens", None),
            )

        choices = getattr(response, "choices", None) or []
        if not choices:
            logger.error("Groq empty choices model=%s", model)
            raise LLMError("Groq returned empty choices", category="empty_response")

        choice0 = choices[0]
        finish = getattr(choice0, "finish_reason", None)
        msg = getattr(choice0, "message", None)
        content = getattr(msg, "content", None) if msg is not None else None
        if content is None or not isinstance(content, str) or not content.strip():
            logger.warning("Groq empty content model=%s finish_reason=%s", model, finish)
            raise LLMError(
                f"Groq returned empty content (finish_reason={finish})",
                category="empty_response",
            )

        logger.info(
            "Groq OK model=%s content_chars=%s finish_reason=%s",
            model,
            len(content),
            finish,
        )
        return content

    def _create(self, system_prompt: str, user_prompt: str) -> str:
        models = self._model_candidates
        last_err: Optional[BaseException] = None
        for idx, model in enumerate(models):
            try:
                return self._create_with_model(model, system_prompt, user_prompt)
            except Exception as e:
                last_err = e
                if _is_model_not_found_error(e) and idx + 1 < len(models):
                    nxt = models[idx + 1]
                    logger.warning(
                        "Groq model %s unavailable — trying fallback %s",
                        model,
                        nxt,
                    )
                    self.model = nxt
                    continue
                raise
        raise last_err or LLMError("Groq generate failed", category="unknown")

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        timeout_s = float(os.getenv("LLM_TIMEOUT_SECONDS", "75"))
        max_retries = max(0, min(int(os.getenv("LLM_MAX_RETRIES", "2")), 4))
        last_err: Optional[BaseException] = None

        for attempt in range(max_retries + 1):
            fut = self._pool.submit(self._create, system_prompt, user_prompt)
            try:
                content = fut.result(timeout=timeout_s)
                if attempt > 0:
                    logger.info("Groq succeeded on retry attempt=%s model=%s", attempt + 1, self.model)
                return content
            except FuturesTimeout as e:
                last_err = LLMTimeoutError(
                    f"Groq exceeded {timeout_s}s",
                    timeout_seconds=timeout_s,
                )
                logger.error(
                    "Groq thread timeout attempt=%s/%s LLM_TIMEOUT_SECONDS=%s model=%s",
                    attempt + 1,
                    max_retries + 1,
                    timeout_s,
                    self.model,
                )
                if attempt < max_retries:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise last_err from e
            except Exception as e:
                last_err = e
                cat, code = classify_llm_failure(e)
                logger.error(
                    "Groq generate failed attempt=%s/%s category=%s status=%s err_type=%s msg=%s",
                    attempt + 1,
                    max_retries + 1,
                    cat,
                    code,
                    type(e).__name__,
                    str(e)[:400],
                )
                if attempt < max_retries and _is_retryable_groq_error(e):
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise

        raise last_err or LLMError("Groq generate failed", category="unknown")


def get_llm_provider() -> LLMProvider:
    """
    Groq when GROQ_API_KEY is set; otherwise MockLLM (safe for boot without secrets).
    OPENAI_API_KEY is logged but not used — generation is Groq-only in this stack.
    """
    groq_api_key = _groq_api_key()
    openai_key = _openai_api_key()

    if openai_key and not groq_api_key:
        logger.warning(
            "OPENAI_API_KEY is set but GROQ_API_KEY is missing — this API uses Groq only; "
            "set GROQ_API_KEY on Railway for AI-generated answers."
        )

    if groq_api_key:
        if not groq_api_key.startswith("gsk_"):
            logger.warning(
                "GROQ_API_KEY does not start with 'gsk_' — key may be invalid (%s)",
                _groq_key_diagnostics(),
            )
        logger.info("LLM provider=GroqProvider %s", _groq_key_diagnostics())
        return GroqProvider(groq_api_key)
    logger.warning(
        "LLM provider=MockLLM (%s). Set GROQ_API_KEY on Railway for live Groq answers.",
        _groq_key_diagnostics(),
    )
    return MockLLM()
