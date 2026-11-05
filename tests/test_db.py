"""Tests for database persistence layer and deduplication."""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

from app.db import (
    _event_fingerprint,
    deduplicate_events,
    SCHEMA_SQL,
)
from models.user_profile import Event


class TestEventFingerprint:
    def test_same_event_same_hash(self):
        fp1 = _event_fingerprint("Jazz Night", "SFJAZZ Center", "2026-11-05")
        fp2 = _event_fingerprint("Jazz Night", "SFJAZZ Center", "2026-11-05")
        assert fp1 == fp2

    def test_case_insensitive(self):
        fp1 = _event_fingerprint("Jazz Night", "SFJAZZ Center", "2026-11-05")
        fp2 = _event_fingerprint("jazz night", "sfjazz center", "2026-11-05")
        assert fp1 == fp2

    def test_different_events_different_hash(self):
        fp1 = _event_fingerprint("Jazz Night", "SFJAZZ Center", "2026-11-05")
        fp2 = _event_fingerprint("Rock Concert", "The Fillmore", "2026-11-05")
        assert fp1 != fp2

    def test_different_date_different_hash(self):
        fp1 = _event_fingerprint("Jazz Night", "SFJAZZ Center", "2026-11-05")
        fp2 = _event_fingerprint("Jazz Night", "SFJAZZ Center", "2026-11-06")
        assert fp1 != fp2

    def test_strips_whitespace(self):
        fp1 = _event_fingerprint("  Jazz Night  ", "SFJAZZ Center", "2026-11-05")
        fp2 = _event_fingerprint("Jazz Night", "SFJAZZ Center", "2026-11-05")
        assert fp1 == fp2


class TestDeduplication:
    def _make_event(self, title: str, venue: str, source: str) -> Event:
        return Event(
            id=f"{source}-1",
            title=title,
            source=source,
            venue_name=venue,
        )

    def test_removes_duplicates_across_sources(self):
        events = [
            self._make_event("Jazz Night", "SFJAZZ Center", "ticketmaster"),
            self._make_event("Jazz Night", "SFJAZZ Center", "eventbrite"),
            self._make_event("Rock Concert", "The Fillmore", "ticketmaster"),
        ]
        result = deduplicate_events(events, "2026-11-05")
        assert len(result) == 2
        assert result[0].source == "ticketmaster"

    def test_keeps_unique_events(self):
        events = [
            self._make_event("Jazz Night", "SFJAZZ Center", "ticketmaster"),
            self._make_event("Rock Concert", "The Fillmore", "eventbrite"),
            self._make_event("Comedy Show", "Cobb's", "seatgeek"),
        ]
        result = deduplicate_events(events, "2026-11-05")
        assert len(result) == 3

    def test_empty_list(self):
        assert deduplicate_events([], "2026-11-05") == []

    def test_case_insensitive_dedup(self):
        events = [
            self._make_event("Jazz Night", "SFJAZZ Center", "source1"),
            self._make_event("jazz night", "sfjazz center", "source2"),
        ]
        result = deduplicate_events(events, "2026-11-05")
        assert len(result) == 1


class TestSchemaSQL:
    def test_schema_has_tables(self):
        assert "user_kbs" in SCHEMA_SQL
        assert "event_cache" in SCHEMA_SQL

    def test_schema_has_indexes(self):
        assert "idx_event_cache_city_date" in SCHEMA_SQL
        assert "idx_event_cache_fetched" in SCHEMA_SQL


class TestDbNoOp:
    """When Supabase is not configured, all operations gracefully no-op."""

    def test_is_available_false_without_config(self):
        with patch("app.db.settings") as mock_settings:
            mock_settings.supabase_url = ""
            mock_settings.supabase_key = ""
            import app.db
            app.db._client = None
            app.db._available = False
            from app.db import is_available
            assert is_available() is False

    @pytest.mark.asyncio
    async def test_save_kb_noop(self):
        with patch("app.db._get_client", return_value=None):
            from app.db import save_user_kb
            result = await save_user_kb("test-user", {"user_id": "test-user"})
            assert result is False

    @pytest.mark.asyncio
    async def test_load_kb_noop(self):
        with patch("app.db._get_client", return_value=None):
            from app.db import load_user_kb
            result = await load_user_kb("test-user")
            assert result is None

    @pytest.mark.asyncio
    async def test_cache_events_noop(self):
        with patch("app.db._get_client", return_value=None):
            from app.db import cache_events
            result = await cache_events([{"title": "test"}], "bay-area", "2026-11-05")
            assert result == 0

    @pytest.mark.asyncio
    async def test_get_cached_events_noop(self):
        with patch("app.db._get_client", return_value=None):
            from app.db import get_cached_events
            result = await get_cached_events("bay-area", "2026-11-05")
            assert result is None
