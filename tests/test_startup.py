"""Tests for startup health checks."""
from __future__ import annotations

import pytest
from unittest.mock import patch


class TestValidateSecrets:
    @pytest.mark.asyncio
    async def test_no_keys_configured(self):
        with patch("app.startup.settings") as mock_settings:
            mock_settings.groq_api_key = ""
            mock_settings.luma_api_key = ""
            mock_settings.eventbrite_api_key = ""
            mock_settings.google_places_api_key = ""
            mock_settings.ticketmaster_api_key = ""
            mock_settings.yelp_api_key = ""
            mock_settings.seatgeek_client_id = ""
            mock_settings.supabase_url = ""
            mock_settings.supabase_key = ""

            from app.startup import validate_secrets
            checks = await validate_secrets()

            assert checks["groq_api_key"] is False
            assert checks["any_event_source"] is False
            assert checks["supabase"] is False
            assert checks["supabase_connected"] is False

    @pytest.mark.asyncio
    async def test_groq_key_present(self):
        with patch("app.startup.settings") as mock_settings:
            mock_settings.groq_api_key = "test-key"
            mock_settings.luma_api_key = ""
            mock_settings.eventbrite_api_key = ""
            mock_settings.google_places_api_key = ""
            mock_settings.ticketmaster_api_key = ""
            mock_settings.yelp_api_key = ""
            mock_settings.seatgeek_client_id = ""
            mock_settings.supabase_url = ""
            mock_settings.supabase_key = ""

            from app.startup import validate_secrets
            checks = await validate_secrets()

            assert checks["groq_api_key"] is True
            assert checks["any_event_source"] is False

    @pytest.mark.asyncio
    async def test_some_sources_configured(self):
        with patch("app.startup.settings") as mock_settings:
            mock_settings.groq_api_key = "test-key"
            mock_settings.luma_api_key = ""
            mock_settings.eventbrite_api_key = ""
            mock_settings.google_places_api_key = ""
            mock_settings.ticketmaster_api_key = "tm-key"
            mock_settings.yelp_api_key = "yelp-key"
            mock_settings.seatgeek_client_id = ""
            mock_settings.supabase_url = ""
            mock_settings.supabase_key = ""

            from app.startup import validate_secrets
            checks = await validate_secrets()

            assert checks["any_event_source"] is True
