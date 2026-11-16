"""
LLM client — Groq primary, OpenRouter failover (both OpenAI-compatible).

Groq: Qwen3-32B, free tier (30 req/min).
OpenRouter: free-tier model only (enforced by pinned :free model ID).
"""
from __future__ import annotations

import time

import structlog
from openai import AsyncOpenAI

from app.config import settings
from sources.http_utils import get_limiter

log = structlog.get_logger()

LLM_TIMEOUT = 30
LLM_MAX_RETRIES = 2


def _get_groq_client() -> AsyncOpenAI:
    """Return an async OpenAI client pointed at Groq."""
    return AsyncOpenAI(
        api_key=settings.groq_api_key,
        base_url=settings.llm_base_url,
        timeout=LLM_TIMEOUT,
        max_retries=LLM_MAX_RETRIES,
    )


def _get_openrouter_client() -> AsyncOpenAI:
    """Return an async OpenAI client pointed at OpenRouter."""
    return AsyncOpenAI(
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        timeout=LLM_TIMEOUT,
        max_retries=LLM_MAX_RETRIES,
    )


KNOWN_FREE_MODELS = frozenset({
    "qwen/qwen3-32b:free",
    "meta-llama/llama-3-8b-instruct:free",
    "meta-llama/llama-3.1-8b-instruct:free",
    "mistralai/mistral-7b-instruct:free",
    "google/gemma-2-9b-it:free",
    "huggingfaceh4/zephyr-7b-beta:free",
})


def _validate_free_model(model_id: str) -> str:
    """Guard: only allow known free OpenRouter models.

    Two checks: must end with :free AND must be in the allowlist.
    This prevents gaming the guard by appending :free to a paid model ID.
    """
    if not model_id.endswith(":free"):
        raise ValueError(
            f"OpenRouter model '{model_id}' is not a free model. "
            "Only models ending with ':free' are allowed in this project."
        )
    if model_id not in KNOWN_FREE_MODELS:
        raise ValueError(
            f"OpenRouter model '{model_id}' is not in the known free models allowlist. "
            "Add it to KNOWN_FREE_MODELS in app/llm.py after verifying it is genuinely free."
        )
    return model_id


# Keep the old name for any callers that import it directly
def get_llm_client() -> AsyncOpenAI:
    """Return the primary (Groq) LLM client."""
    return _get_groq_client()


async def chat(
    messages: list[dict],
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> str:
    """Send a chat completion — Groq first, OpenRouter failover on error."""
    limiter = get_limiter("llm")
    await limiter.acquire()

    temperature = temperature or settings.llm_temperature
    max_tokens = max_tokens or settings.llm_max_tokens

    # --- Try Groq (primary) ---
    if settings.groq_api_key:
        try:
            return await _call_provider(
                client=_get_groq_client(),
                model=settings.llm_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                provider="groq",
            )
        except Exception as groq_exc:
            log.warning(
                "llm.groq_failed",
                error=str(groq_exc),
                msg="Falling back to OpenRouter",
            )
            if not settings.openrouter_api_key:
                raise

    # --- Failover: OpenRouter (free model only) ---
    if settings.openrouter_api_key:
        free_model = _validate_free_model(settings.openrouter_model)
        return await _call_provider(
            client=_get_openrouter_client(),
            model=free_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            provider="openrouter",
        )

    raise RuntimeError("No LLM provider configured (need GROQ_API_KEY or OPENROUTER_API_KEY)")


async def _call_provider(
    *,
    client: AsyncOpenAI,
    model: str,
    messages: list[dict],
    temperature: float,
    max_tokens: int,
    provider: str,
) -> str:
    """Call a single LLM provider and log the result."""
    start = time.monotonic()
    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        elapsed = time.monotonic() - start
        usage = resp.usage
        log.info(
            "llm.completion",
            provider=provider,
            model=model,
            latency=round(elapsed, 2),
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
        )
        return resp.choices[0].message.content or ""
    except Exception as exc:
        elapsed = time.monotonic() - start
        log.error(
            "llm.error",
            provider=provider,
            model=model,
            error=str(exc),
            latency=round(elapsed, 2),
        )
        raise
