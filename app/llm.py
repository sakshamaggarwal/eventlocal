"""
LLM client — Qwen3-32B via Groq (OpenAI-compatible).

Includes rate limiting (Groq free tier: 30 req/min) and latency guards.
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


def get_llm_client() -> AsyncOpenAI:
    """Return an async OpenAI client pointed at Groq."""
    return AsyncOpenAI(
        api_key=settings.groq_api_key,
        base_url=settings.llm_base_url,
        timeout=LLM_TIMEOUT,
        max_retries=LLM_MAX_RETRIES,
    )


async def chat(
    messages: list[dict],
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> str:
    """Send a chat completion with rate limiting and latency tracking."""
    limiter = get_limiter("llm")
    await limiter.acquire()

    client = get_llm_client()
    start = time.monotonic()
    try:
        resp = await client.chat.completions.create(
            model=settings.llm_model,
            messages=messages,
            temperature=temperature or settings.llm_temperature,
            max_tokens=max_tokens or settings.llm_max_tokens,
        )
        elapsed = time.monotonic() - start
        usage = resp.usage
        log.info(
            "llm.completion",
            model=settings.llm_model,
            latency=round(elapsed, 2),
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
        )
        return resp.choices[0].message.content or ""
    except Exception as exc:
        elapsed = time.monotonic() - start
        log.error("llm.error", error=str(exc), latency=round(elapsed, 2))
        raise
