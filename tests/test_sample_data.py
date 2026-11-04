"""Tests for sample data and the demo pipeline."""
from __future__ import annotations

from sources.sample_data import get_sample_events
from agents.layers.age_layer import apply_age_scores
from models.user_profile import UserProfile


class TestSampleData:
    def test_returns_events(self):
        events = get_sample_events()
        assert len(events) > 10

    def test_all_events_have_required_fields(self):
        for ev in get_sample_events():
            assert ev.id
            assert ev.title
            assert ev.source in ("luma", "eventbrite", "google_places")

    def test_events_cover_all_sources(self):
        sources = {ev.source for ev in get_sample_events()}
        assert "luma" in sources
        assert "eventbrite" in sources
        assert "google_places" in sources

    def test_scoring_works_with_sample_data(self):
        events = get_sample_events()
        for age in [18, 25, 35, 45, 55]:
            profile = UserProfile(age=age)
            scored = apply_age_scores(events, profile)
            assert len(scored) == len(events)
            assert scored[0].age_score >= scored[-1].age_score
