"""Tests for LLM client — Groq primary + OpenRouter failover."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.llm import _validate_free_model, chat


class TestValidateFreeModel:
    def test_accepts_free_model(self):
        assert _validate_free_model("qwen/qwen3-32b:free") == "qwen/qwen3-32b:free"

    def test_accepts_other_free_model(self):
        assert _validate_free_model("meta-llama/llama-3-8b-instruct:free") == "meta-llama/llama-3-8b-instruct:free"

    def test_rejects_paid_model(self):
        with pytest.raises(ValueError, match="not a free model"):
            _validate_free_model("anthropic/claude-3-sonnet")

    def test_rejects_model_without_free_suffix(self):
        with pytest.raises(ValueError, match="not a free model"):
            _validate_free_model("qwen/qwen3-32b")

    def test_rejects_paid_model_with_free_suffix(self):
        """Edge case: paid model with :free appended should be blocked by allowlist."""
        with pytest.raises(ValueError, match="not in the known free models allowlist"):
            _validate_free_model("anthropic/claude-3-sonnet:free")

    def test_rejects_unknown_free_suffixed_model(self):
        with pytest.raises(ValueError, match="not in the known free models allowlist"):
            _validate_free_model("openai/gpt-4o:free")


def _mock_completion(content: str = "test response"):
    """Build a mock chat completion response."""
    usage = MagicMock()
    usage.prompt_tokens = 10
    usage.completion_tokens = 20
    message = MagicMock()
    message.content = content
    choice = MagicMock()
    choice.message = message
    resp = MagicMock()
    resp.usage = usage
    resp.choices = [choice]
    return resp


class TestChatFailover:
    @pytest.mark.asyncio
    async def test_groq_primary_success(self):
        """When Groq succeeds, OpenRouter is never called."""
        with patch("app.llm.settings") as mock_settings, \
             patch("app.llm._get_groq_client") as mock_groq, \
             patch("app.llm._get_openrouter_client") as mock_or:
            mock_settings.groq_api_key = "groq-key"
            mock_settings.openrouter_api_key = "or-key"
            mock_settings.llm_model = "qwen3-32b"
            mock_settings.llm_temperature = 0.7
            mock_settings.llm_max_tokens = 4096
            mock_settings.openrouter_model = "qwen/qwen3-32b:free"

            groq_client = AsyncMock()
            groq_client.chat.completions.create = AsyncMock(
                return_value=_mock_completion("groq response")
            )
            mock_groq.return_value = groq_client

            result = await chat([{"role": "user", "content": "hello"}])

            assert result == "groq response"
            groq_client.chat.completions.create.assert_awaited_once()
            mock_or.assert_not_called()

    @pytest.mark.asyncio
    async def test_failover_to_openrouter(self):
        """When Groq fails, falls back to OpenRouter."""
        with patch("app.llm.settings") as mock_settings, \
             patch("app.llm._get_groq_client") as mock_groq, \
             patch("app.llm._get_openrouter_client") as mock_or:
            mock_settings.groq_api_key = "groq-key"
            mock_settings.openrouter_api_key = "or-key"
            mock_settings.llm_model = "qwen3-32b"
            mock_settings.llm_temperature = 0.7
            mock_settings.llm_max_tokens = 4096
            mock_settings.openrouter_model = "qwen/qwen3-32b:free"
            mock_settings.openrouter_base_url = "https://openrouter.ai/api/v1"

            groq_client = AsyncMock()
            groq_client.chat.completions.create = AsyncMock(
                side_effect=RuntimeError("Groq rate limit")
            )
            mock_groq.return_value = groq_client

            or_client = AsyncMock()
            or_client.chat.completions.create = AsyncMock(
                return_value=_mock_completion("openrouter response")
            )
            mock_or.return_value = or_client

            result = await chat([{"role": "user", "content": "hello"}])

            assert result == "openrouter response"
            or_client.chat.completions.create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_openrouter_only_when_no_groq(self):
        """When only OpenRouter is configured, it's used directly."""
        with patch("app.llm.settings") as mock_settings, \
             patch("app.llm._get_openrouter_client") as mock_or:
            mock_settings.groq_api_key = ""
            mock_settings.openrouter_api_key = "or-key"
            mock_settings.llm_temperature = 0.7
            mock_settings.llm_max_tokens = 4096
            mock_settings.openrouter_model = "qwen/qwen3-32b:free"
            mock_settings.openrouter_base_url = "https://openrouter.ai/api/v1"

            or_client = AsyncMock()
            or_client.chat.completions.create = AsyncMock(
                return_value=_mock_completion("openrouter only")
            )
            mock_or.return_value = or_client

            result = await chat([{"role": "user", "content": "hello"}])

            assert result == "openrouter only"

    @pytest.mark.asyncio
    async def test_no_keys_raises(self):
        """With no LLM keys, raises RuntimeError."""
        with patch("app.llm.settings") as mock_settings:
            mock_settings.groq_api_key = ""
            mock_settings.openrouter_api_key = ""

            with pytest.raises(RuntimeError, match="No LLM provider configured"):
                await chat([{"role": "user", "content": "hello"}])

    @pytest.mark.asyncio
    async def test_paid_model_rejected_on_failover(self):
        """If openrouter_model doesn't end with :free, failover raises ValueError."""
        with patch("app.llm.settings") as mock_settings, \
             patch("app.llm._get_groq_client") as mock_groq:
            mock_settings.groq_api_key = "groq-key"
            mock_settings.openrouter_api_key = "or-key"
            mock_settings.llm_model = "qwen3-32b"
            mock_settings.llm_temperature = 0.7
            mock_settings.llm_max_tokens = 4096
            mock_settings.openrouter_model = "anthropic/claude-3-sonnet"

            groq_client = AsyncMock()
            groq_client.chat.completions.create = AsyncMock(
                side_effect=RuntimeError("Groq down")
            )
            mock_groq.return_value = groq_client

            with pytest.raises(ValueError, match="not a free model"):
                await chat([{"role": "user", "content": "hello"}])
