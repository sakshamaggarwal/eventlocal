"""Tests for knowledge base persistence and scoring."""
from __future__ import annotations

import pytest
from models.user_profile import Event, UserProfile
from knowledge.cognee_engine import (
    UserFeedback,
    UserKnowledgeBase,
    get_user_kb,
    restore_user_kb,
    export_all_kbs,
)
from agents.layers.age_layer import apply_age_scores, score_social


class TestUserFeedbackSerialization:
    def test_roundtrip(self):
        fb = UserFeedback(
            event_id="ev-1",
            action="chosen",
            value=1.0,
            timestamp=1234567890.0,
            tags=["jazz", "live-music"],
        )
        d = fb.to_dict()
        restored = UserFeedback.from_dict(d)
        assert restored.event_id == "ev-1"
        assert restored.action == "chosen"
        assert restored.value == 1.0
        assert restored.tags == ["jazz", "live-music"]

    def test_from_dict_defaults(self):
        fb = UserFeedback.from_dict({"event_id": "ev-2", "action": "skipped"})
        assert fb.value == 0.0
        assert fb.tags == []


class TestUserKBSerialization:
    def test_roundtrip(self):
        kb = UserKnowledgeBase(user_id="u-1")
        kb.query_history = ["jazz tonight", "rooftop bars"]
        kb.preferred_tags = {"jazz": 1.5, "rooftop": 0.8}
        kb.avoided_tags = {"loud": 0.3}
        kb.preferred_venues = {"SFJAZZ Center": 2.0}
        kb.record_feedback(
            Event(id="ev-1", title="Jazz Night", source="test", tags=["jazz"]),
            "chosen",
            1.0,
        )

        d = kb.to_dict()
        restored = UserKnowledgeBase.from_dict(d)

        assert restored.user_id == "u-1"
        assert restored.query_history == ["jazz tonight", "rooftop bars"]
        assert restored.preferred_tags["jazz"] > 0
        assert len(restored.feedback) == 1
        assert restored.feedback[0].event_id == "ev-1"

    def test_empty_roundtrip(self):
        kb = UserKnowledgeBase(user_id="empty")
        d = kb.to_dict()
        restored = UserKnowledgeBase.from_dict(d)
        assert restored.user_id == "empty"
        assert restored.query_history == []
        assert restored.feedback == []


class TestKBPersistenceFunctions:
    def test_restore_and_export(self):
        data = {
            "user_id": "persist-test",
            "query_history": ["clubs SF"],
            "feedback": [],
            "preferred_vibes": {},
            "preferred_venues": {},
            "preferred_tags": {"nightclub": 1.0},
            "avoided_tags": {},
        }
        kb = restore_user_kb("persist-test", data)
        assert kb.preferred_tags["nightclub"] == 1.0

        exported = export_all_kbs()
        assert "persist-test" in exported
        assert exported["persist-test"]["preferred_tags"]["nightclub"] == 1.0

    def test_get_user_kb_creates_new(self):
        kb = get_user_kb("brand-new-user-xyz")
        assert kb.user_id == "brand-new-user-xyz"
        assert kb.query_history == []


class TestSocialScoring:
    def _make_event(self, title: str, tags: list[str]) -> Event:
        return Event(
            id="test", title=title, source="test",
            description=title, tags=tags,
        )

    def test_solo_boosts_quiet(self):
        ev = self._make_event("Quiet Jazz Cafe", ["jazz", "cafe"])
        profile = UserProfile(age=28, social_mode="solo")
        score = score_social(ev, profile)
        assert score > 0.5

    def test_solo_penalizes_group(self):
        ev = self._make_event("Big Group Party Night", ["party", "group"])
        profile = UserProfile(age=28, social_mode="solo")
        score = score_social(ev, profile)
        assert score < 0.5

    def test_date_boosts_romantic(self):
        ev = self._make_event("Romantic Rooftop Cocktail", ["cocktail", "rooftop", "romantic"])
        profile = UserProfile(age=30, social_mode="date")
        score = score_social(ev, profile)
        assert score > 0.5

    def test_group_boosts_party(self):
        ev = self._make_event("Karaoke Bar Party", ["karaoke", "party", "bar-crawl"])
        profile = UserProfile(age=25, social_mode="group")
        score = score_social(ev, profile)
        assert score > 0.5

    def test_composite_score_blends(self):
        ev = self._make_event("Jazz Bar Night", ["jazz", "cocktail"])
        profile = UserProfile(age=35, social_mode="date")
        events = apply_age_scores([ev], profile)
        assert events[0].age_score > 0
        assert events[0].social_score > 0
        assert 0 < events[0].composite_score <= 1.0
