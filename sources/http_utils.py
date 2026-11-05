"""
Shared HTTP utilities — rate limiting and retries with backoff.

Each source gets its own rate limiter so one slow API can't block others.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx
import structlog

log = structlog.get_logger()


class RateLimiter:
    """Token-bucket rate limiter (per-source)."""

    def __init__(self, calls_per_minute: int = 60) -> None:
        self._rate = calls_per_minute
        self._tokens = float(calls_per_minute)
        self._max = float(calls_per_minute)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            self._tokens = min(self._max, self._tokens + elapsed * (self._rate / 60.0))
            self._last_refill = now

            if self._tokens < 1.0:
                wait = (1.0 - self._tokens) / (self._rate / 60.0)
                log.debug("rate_limiter.waiting", seconds=round(wait, 2))
                await asyncio.sleep(wait)
                self._tokens = 0.0
            else:
                self._tokens -= 1.0


# Per-source rate limiters (calls/minute)
_limiters: dict[str, RateLimiter] = {}

SOURCE_RATE_LIMITS = {
    "ticketmaster": 80,   # 5000/day ≈ 3.5/min, generous burst
    "yelp": 80,           # 5000/day
    "seatgeek": 120,      # no hard limit
    "luma": 60,
    "eventbrite": 60,
    "google_places": 60,
    "llm": 30,            # Groq free tier: 30 req/min
}


def get_limiter(source: str) -> RateLimiter:
    if source not in _limiters:
        rpm = SOURCE_RATE_LIMITS.get(source, 60)
        _limiters[source] = RateLimiter(rpm)
    return _limiters[source]


async def fetch_with_retry(
    url: str,
    *,
    source: str,
    params: dict | None = None,
    headers: dict | None = None,
    max_retries: int = 3,
    timeout: int = 15,
) -> httpx.Response:
    """
    HTTP GET with rate limiting and exponential backoff.

    Raises on final failure so callers can handle it.
    """
    limiter = get_limiter(source)
    last_exc: Exception | None = None

    for attempt in range(max_retries):
        await limiter.acquire()
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(url, params=params, headers=headers)
                resp.raise_for_status()
                return resp
        except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.ConnectError) as exc:
            last_exc = exc
            if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code < 500:
                if exc.response.status_code != 429:
                    raise
            wait = 2 ** attempt
            log.warning(
                "http.retry",
                source=source,
                attempt=attempt + 1,
                wait=wait,
                error=str(exc),
            )
            await asyncio.sleep(wait)

    raise last_exc or RuntimeError(f"fetch_with_retry failed for {source}")
