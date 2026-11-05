"""Tests for sample event data used in demo mode."""
from __future__ import annotations

import pytest
from sources.sample_data import get_sample_events
from models.user_profile import Event


class TestSampleData:
    def test_returns_events(self):
        events = get_sample_events()
        assert len(events) == 16

    def test_all_events_are_event_instances(self):
        events = get_sample_events()
        for ev in events:
            assert isinstance(ev, Event)

    def test_all_sources_covered(self):
        events = get_sample_events()
        sources = {ev.source for ev in events}
        assert "luma" in sources
        assert "eventbrite" in sources
        assert "google_places" in sources

    def test_events_have_required_fields(self):
        events = get_sample_events()
        for ev in events:
            assert ev.id
            assert ev.title
            assert ev.source

    def test_events_have_tags(self):
        events = get_sample_events()
        for ev in events:
            assert len(ev.tags) > 0, f"Event {ev.id} has no tags"

    def test_custom_date(self):
        events = get_sample_events(target_date="2026-12-25")
        luma_events = [e for e in events if e.source == "luma"]
        for ev in luma_events:
            assert "2026-12-25" in ev.start_time

    def test_all_ids_unique(self):
        events = get_sample_events()
        ids = [ev.id for ev in events]
        assert len(ids) == len(set(ids))
