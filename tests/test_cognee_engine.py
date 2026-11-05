"""Tests for knowledge/cognee_engine.py — two-tier KB, user KB, feedback loop."""
from __future__ import annotations

import pytest

from knowledge.cognee_engine import (
    TwoTierCogneeEngine,
    CogneeEngine,
    UserKnowledgeBase,
    UserFeedback,
    get_user_kb,
    _user_kbs,
)
from models.user_profile import Event


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_event():
    return Event(
        id="ev-001",
        title="Jazz at The Blue Note",
        description="Live jazz quartet, intimate setting",
        source="luma",
        venue_name="The Blue Note",
        venue_address="123 Mission St",
        start_time="2026-11-05T20:00:00",
        price="$25",
        tags=["jazz", "live-music", "cocktails"],
    )


@pytest.fixture
def sample_event_edm():
    return Event(
        id="ev-002",
        title="Neon Nights EDM",
        description="EDM rave at the warehouse",
        source="eventbrite",
        venue_name="Warehouse 9",
        start_time="2026-11-05T22:00:00",
        price="$30",
        tags=["edm", "rave", "nightclub"],
    )


@pytest.fixture(autouse=True)
def clear_user_kbs():
    """Clear the in-memory user KB store between tests."""
    _user_kbs.clear()
    yield
    _user_kbs.clear()


# ---------------------------------------------------------------------------
# UserKnowledgeBase
# ---------------------------------------------------------------------------

class TestUserKnowledgeBase:
    def test_init(self):
        kb = UserKnowledgeBase(user_id="user-1")
        assert kb.user_id == "user-1"
        assert kb.query_history == []
        assert kb.feedback == []

    def test_record_query(self):
        kb = UserKnowledgeBase(user_id="user-1")
        kb.record_query("jazz events tonight")
        kb.record_query("best cocktail bars")
        assert len(kb.query_history) == 2
        assert kb.query_history[0] == "jazz events tonight"

    def test_record_feedback_chosen(self, sample_event):
        kb = UserKnowledgeBase(user_id="user-1")
        kb.record_feedback(sample_event, "chosen", 1.0)
        assert len(kb.feedback) == 1
        assert kb.feedback[0].action == "chosen"
        assert kb.feedback[0].event_id == "ev-001"
        assert "jazz" in kb.preferred_tags
        assert kb.preferred_tags["jazz"] > 0

    def test_record_feedback_skipped(self, sample_event_edm):
        kb = UserKnowledgeBase(user_id="user-1")
        kb.record_feedback(sample_event_edm, "skipped", 0.0)
        assert len(kb.feedback) == 1
        assert "edm" in kb.avoided_tags

    def test_record_feedback_rated_high(self, sample_event):
        kb = UserKnowledgeBase(user_id="user-1")
        kb.record_feedback(sample_event, "rated", 5.0)
        assert "jazz" in kb.preferred_tags
        assert kb.preferred_tags["jazz"] > 0

    def test_record_feedback_rated_low(self, sample_event):
        kb = UserKnowledgeBase(user_id="user-1")
        kb.record_feedback(sample_event, "rated", 1.0)
        assert "jazz" in kb.avoided_tags

    def test_venue_preference_tracked(self, sample_event):
        kb = UserKnowledgeBase(user_id="user-1")
        kb.record_feedback(sample_event, "chosen", 1.0)
        assert "The Blue Note" in kb.preferred_venues
        assert kb.preferred_venues["The Blue Note"] > 0

    def test_preference_context_empty(self):
        kb = UserKnowledgeBase(user_id="user-1")
        assert kb.get_preference_context() == ""

    def test_preference_context_with_data(self, sample_event, sample_event_edm):
        kb = UserKnowledgeBase(user_id="user-1")
        kb.record_query("jazz events")
        kb.record_feedback(sample_event, "chosen", 1.0)
        kb.record_feedback(sample_event_edm, "skipped", 0.0)
        context = kb.get_preference_context()
        assert "jazz" in context
        assert "Recent searches" in context

    def test_multiple_feedback_accumulates(self, sample_event):
        kb = UserKnowledgeBase(user_id="user-1")
        kb.record_feedback(sample_event, "chosen", 1.0)
        kb.record_feedback(sample_event, "chosen", 1.0)
        assert kb.preferred_tags["jazz"] == pytest.approx(0.2)


# ---------------------------------------------------------------------------
# get_user_kb
# ---------------------------------------------------------------------------

class TestGetUserKB:
    def test_creates_new(self):
        kb = get_user_kb("new-user")
        assert kb.user_id == "new-user"

    def test_returns_existing(self):
        kb1 = get_user_kb("user-1")
        kb1.record_query("test query")
        kb2 = get_user_kb("user-1")
        assert kb2.query_history == ["test query"]
        assert kb1 is kb2


# ---------------------------------------------------------------------------
# TwoTierCogneeEngine
# ---------------------------------------------------------------------------

class TestTwoTierCogneeEngine:
    def test_backward_compat_alias(self):
        assert CogneeEngine is TwoTierCogneeEngine

    def test_init(self):
        engine = TwoTierCogneeEngine()
        assert engine._initialized is False

    def test_weights(self):
        engine = TwoTierCogneeEngine()
        assert engine.USER_WEIGHT == 1.5
        assert engine.GLOBAL_WEIGHT == 1.0

    def test_merge_results_no_prefs(self):
        engine = TwoTierCogneeEngine()
        kb = UserKnowledgeBase(user_id="user-1")
        result = engine._merge_results("global context here", kb)
        assert result == "global context here"

    def test_merge_results_with_prefs(self, sample_event):
        engine = TwoTierCogneeEngine()
        kb = UserKnowledgeBase(user_id="user-1")
        kb.record_feedback(sample_event, "chosen", 1.0)
        result = engine._merge_results("global context here", kb)
        assert "Global Knowledge" in result
        assert "Personal Context" in result
        assert "jazz" in result
        assert "1.5" in result

    @pytest.mark.asyncio
    async def test_search_without_cognee(self):
        engine = TwoTierCogneeEngine()
        result = await engine.search("jazz events tonight")
        assert result == ""

    @pytest.mark.asyncio
    async def test_search_records_user_query(self):
        engine = TwoTierCogneeEngine()
        await engine.search("jazz events", user_id="user-1")
        kb = get_user_kb("user-1")
        assert "jazz events" in kb.query_history

    @pytest.mark.asyncio
    async def test_record_event_chosen(self, sample_event):
        engine = TwoTierCogneeEngine()
        await engine.record_event_chosen("user-1", sample_event)
        kb = get_user_kb("user-1")
        assert len(kb.feedback) == 1
        assert kb.feedback[0].action == "chosen"

    @pytest.mark.asyncio
    async def test_record_event_skipped(self, sample_event):
        engine = TwoTierCogneeEngine()
        await engine.record_event_skipped("user-1", sample_event)
        kb = get_user_kb("user-1")
        assert len(kb.feedback) == 1
        assert kb.feedback[0].action == "skipped"

    @pytest.mark.asyncio
    async def test_record_event_rated(self, sample_event):
        engine = TwoTierCogneeEngine()
        await engine.record_event_rated("user-1", sample_event, 4.5)
        kb = get_user_kb("user-1")
        assert len(kb.feedback) == 1
        assert kb.feedback[0].value == 4.5

    def test_get_user_stats(self, sample_event):
        engine = TwoTierCogneeEngine()
        kb = get_user_kb("user-1")
        kb.record_query("test")
        kb.record_feedback(sample_event, "chosen", 1.0)
        stats = engine.get_user_stats("user-1")
        assert stats["queries"] == 1
        assert stats["feedback_count"] == 1
        assert stats["preferred_tags"] > 0

    @pytest.mark.asyncio
    async def test_remember_without_cognee(self):
        engine = TwoTierCogneeEngine()
        await engine.remember()  # should not raise

    @pytest.mark.asyncio
    async def test_ingest_events_without_cognee(self, sample_event):
        engine = TwoTierCogneeEngine()
        await engine.ingest_events([sample_event])  # should not raise

    @pytest.mark.asyncio
    async def test_ingest_reviews_without_cognee(self):
        engine = TwoTierCogneeEngine()
        await engine.ingest_reviews(
            [{"rating": 4, "text": "great vibe"}], "The Blue Note"
        )  # should not raise

    @pytest.mark.asyncio
    async def test_ingest_training_without_cognee(self):
        engine = TwoTierCogneeEngine()
        await engine.ingest_training_data("some training text")  # should not raise
