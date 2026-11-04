"""Tests for age personalization layer."""
from __future__ import annotations

import pytest
from agents.layers.age_layer import apply_age_scores, score_event
from models.user_profile import AgeBracket, Event, UserProfile


def _make_event(**kwargs) -> Event:
    defaults = dict(id="test-1", title="Test Event", source="test")
    defaults.update(kwargs)
    return Event(**defaults)


class TestScoreEvent:
    def test_neutral_baseline(self):
        event = _make_event(title="Generic community event")
        profile = UserProfile(age=25)
        score = score_event(event, profile)
        assert score == 0.5

    def test_boost_keywords_increase_score(self):
        event = _make_event(
            title="Rooftop Happy Hour with EDM",
            tags=["nightclub", "rooftop", "happy-hour"],
        )
        profile = UserProfile(age=25)
        score = score_event(event, profile)
        assert score > 0.5

    def test_penalize_keywords_decrease_score(self):
        event = _make_event(
            title="Senior retirement community meetup",
            tags=["senior", "retirement"],
        )
        profile = UserProfile(age=25)
        score = score_event(event, profile)
        assert score < 0.5

    def test_under_21_boosts_gaming(self):
        event = _make_event(title="Esports gaming tournament", tags=["gaming", "esports", "all-ages"])
        profile = UserProfile(age=18)
        score = score_event(event, profile)
        assert score >= 0.7

    def test_fifties_plus_boosts_classical(self):
        event = _make_event(title="Classical music at the opera house", tags=["classical", "opera"])
        profile = UserProfile(age=55)
        score = score_event(event, profile)
        assert score >= 0.7

    def test_score_clamped_between_0_and_1(self):
        event = _make_event(
            title="all-ages teen anime gaming esports boba college fun",
            tags=["all-ages", "teen", "anime", "gaming", "esports", "boba", "college"],
        )
        profile = UserProfile(age=18)
        score = score_event(event, profile)
        assert 0.0 <= score <= 1.0


class TestApplyAgeScores:
    def test_sorts_by_score_descending(self):
        events = [
            _make_event(id="low", title="Wine tasting gala"),
            _make_event(id="high", title="Tech meetup rooftop happy-hour"),
        ]
        profile = UserProfile(age=25)
        scored = apply_age_scores(events, profile)
        assert scored[0].age_score >= scored[-1].age_score

    def test_all_events_scored(self):
        events = [_make_event(id=f"e-{i}", title=f"Event {i}") for i in range(5)]
        profile = UserProfile(age=30)
        scored = apply_age_scores(events, profile)
        assert len(scored) == 5
        assert all(e.age_score > 0 for e in scored)


class TestAgeBracket:
    @pytest.mark.parametrize("age,expected", [
        (15, AgeBracket.UNDER_21),
        (20, AgeBracket.UNDER_21),
        (21, AgeBracket.TWENTIES),
        (29, AgeBracket.TWENTIES),
        (30, AgeBracket.THIRTIES),
        (39, AgeBracket.THIRTIES),
        (40, AgeBracket.FORTIES),
        (49, AgeBracket.FORTIES),
        (50, AgeBracket.FIFTIES_PLUS),
        (75, AgeBracket.FIFTIES_PLUS),
    ])
    def test_age_to_bracket(self, age, expected):
        assert AgeBracket.from_age(age) == expected
