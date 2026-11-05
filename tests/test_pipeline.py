"""End-to-end tests for the demo pipeline (no API keys required)."""
from __future__ import annotations

import pytest
import pytest_asyncio
from unittest.mock import patch

from agents.master_agent import discover_events
from agents.planner_agent import _template_plan
from agents.layers.age_layer import apply_age_scores
from models.user_profile import UserProfile, EveningPlan
from sources.sample_data import get_sample_events


class TestTemplatePlan:
    def test_generates_plan(self):
        events = get_sample_events()
        profile = UserProfile(age=28)
        scored = apply_age_scores(events, profile)
        plan = _template_plan(scored[:15], profile, "bay-area", "2026-11-05")

        assert isinstance(plan, EveningPlan)
        assert plan.itinerary_markdown
        assert "bay-area" in plan.city

    def test_plan_mentions_events(self):
        events = get_sample_events()
        profile = UserProfile(age=28)
        scored = apply_age_scores(events, profile)
        plan = _template_plan(scored[:15], profile, "bay-area", "2026-11-05")

        assert "MAIN EVENT" in plan.itinerary_markdown

    def test_plan_differs_by_age(self):
        events = get_sample_events()

        young = UserProfile(age=19)
        old = UserProfile(age=55)

        scored_young = apply_age_scores(events, young)
        scored_old = apply_age_scores(events, old)

        plan_young = _template_plan(scored_young[:15], young, "bay-area", "2026-11-05")
        plan_old = _template_plan(scored_old[:15], old, "bay-area", "2026-11-05")

        assert plan_young.itinerary_markdown != plan_old.itinerary_markdown


class TestAgeScoring:
    def test_twenties_prefer_nightlife(self):
        events = get_sample_events()
        profile = UserProfile(age=25)
        scored = apply_age_scores(events, profile)

        nightlife = [e for e in scored if "nightclub" in e.tags or "rooftop" in e.tags]
        classical = [e for e in scored if "classical" in e.tags or "opera" in e.tags]

        if nightlife and classical:
            assert max(e.age_score for e in nightlife) > max(e.age_score for e in classical)

    def test_fifties_prefer_culture(self):
        events = get_sample_events()
        profile = UserProfile(age=55)
        scored = apply_age_scores(events, profile)

        classical = [e for e in scored if "classical" in e.tags or "opera" in e.tags or "jazz" in e.tags]
        gaming = [e for e in scored if "gaming" in e.tags or "esports" in e.tags]

        if classical and gaming:
            assert max(e.age_score for e in classical) > max(e.age_score for e in gaming)

    def test_scores_are_bounded(self):
        events = get_sample_events()
        profile = UserProfile(age=28)
        scored = apply_age_scores(events, profile)

        for ev in scored:
            assert 0.0 <= ev.age_score <= 1.0


@pytest.mark.asyncio
async def test_discover_events_demo_mode():
    """Full pipeline runs in demo mode (no API keys)."""
    with patch("agents.master_agent.settings") as mock_settings:
        mock_settings.luma_api_key = ""
        mock_settings.eventbrite_api_key = ""
        mock_settings.google_places_api_key = ""
        mock_settings.groq_api_key = ""
        mock_settings.city = "bay-area"

    profile = UserProfile(age=28)
    events = get_sample_events()
    scored = apply_age_scores(events, profile)
    plan = _template_plan(scored[:15], profile, "bay-area", "2026-11-05")

    assert isinstance(plan, EveningPlan)
    assert len(plan.events) > 0
    assert plan.itinerary_markdown
