"""Tests for HTTP utilities — rate limiting and retries."""
from __future__ import annotations

import asyncio
import time

import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from sources.http_utils import RateLimiter, get_limiter, fetch_with_retry, SOURCE_RATE_LIMITS


class TestRateLimiter:
    @pytest.mark.asyncio
    async def test_acquire_within_limit(self):
        limiter = RateLimiter(calls_per_minute=60)
        start = time.monotonic()
        await limiter.acquire()
        elapsed = time.monotonic() - start
        assert elapsed < 0.1

    @pytest.mark.asyncio
    async def test_multiple_acquires(self):
        limiter = RateLimiter(calls_per_minute=600)
        for _ in range(5):
            await limiter.acquire()


class TestGetLimiter:
    def test_returns_limiter_for_known_source(self):
        limiter = get_limiter("ticketmaster")
        assert isinstance(limiter, RateLimiter)

    def test_same_source_same_limiter(self):
        l1 = get_limiter("test-source-a")
        l2 = get_limiter("test-source-a")
        assert l1 is l2

    def test_different_source_different_limiter(self):
        l1 = get_limiter("test-source-b")
        l2 = get_limiter("test-source-c")
        assert l1 is not l2


class TestSourceRateLimits:
    def test_all_sources_have_limits(self):
        for source in ["ticketmaster", "yelp", "seatgeek", "luma", "eventbrite", "google_places", "llm"]:
            assert source in SOURCE_RATE_LIMITS


class TestFetchWithRetry:
    @pytest.mark.asyncio
    async def test_success_on_first_try(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()

        with patch("sources.http_utils.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await fetch_with_retry(
                "https://example.com/api",
                source="test-fetch",
            )
            assert result is mock_resp

    @pytest.mark.asyncio
    async def test_retries_on_timeout(self):
        import httpx

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()

        with patch("sources.http_utils.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.side_effect = [
                httpx.TimeoutException("timeout"),
                mock_resp,
            ]
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            result = await fetch_with_retry(
                "https://example.com/api",
                source="test-retry",
                max_retries=3,
            )
            assert result is mock_resp

    @pytest.mark.asyncio
    async def test_raises_after_max_retries(self):
        import httpx

        with patch("sources.http_utils.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.TimeoutException("timeout")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            with pytest.raises(httpx.TimeoutException):
                await fetch_with_retry(
                    "https://example.com/api",
                    source="test-fail",
                    max_retries=2,
                )
