"""
LLM client — Qwen3-32B via Groq (OpenAI-compatible).
"""
from __future__ import annotations

from openai import AsyncOpenAI
from app.config import settings


def get_llm_client() -> AsyncOpenAI:
    """Return an async OpenAI client pointed at Groq."""
    return AsyncOpenAI(
        api_key=settings.groq_api_key,
        base_url=settings.llm_base_url,
    )


async def chat(
    messages: list[dict],
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> str:
    """Send a chat completion and return the assistant's text."""
    client = get_llm_client()
    resp = await client.chat.completions.create(
        model=settings.llm_model,
        messages=messages,
        temperature=temperature or settings.llm_temperature,
        max_tokens=max_tokens or settings.llm_max_tokens,
    )
    return resp.choices[0].message.content or ""
