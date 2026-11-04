"""
Tests for the age personalization layer.
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.layers.age_layer import score_event, apply_age_scores
from models.user_profile import AgeBracket, Event, UserProfile


def _make_event(title: str, tags: list[str] | None = None) -> Event:
    return Event(
        id="test-1",
        title=title,
        source="test",
        tags=tags or [],
    )


def test_twenties_boost_nightclub():
    event = _make_event("Friday Nightclub Rooftop Party", ["nightclub", "rooftop"])
    profile = UserProfile(age=25)
    score = score_event(event, profile)
    assert score > 0.5, f"Nightclub should boost for 25yo, got {score}"


def test_twenties_penalize_senior():
    event = _make_event("Senior Retirement Celebration")
    profile = UserProfile(age=25)
    score = score_event(event, profile)
    assert score < 0.5, f"Senior event should penalize for 25yo, got {score}"


def test_fifties_boost_jazz():
    event = _make_event("Jazz Night at Blue Note", ["jazz", "live-music"])
    profile = UserProfile(age=55)
    score = score_event(event, profile)
    assert score > 0.5, f"Jazz should boost for 55yo, got {score}"


def test_under_21_penalize_cocktail():
    event = _make_event("Cocktail Lounge Evening", ["cocktail-lounge"])
    profile = UserProfile(age=19)
    score = score_event(event, profile)
    assert score <= 0.5, f"Cocktail lounge should not boost for 19yo, got {score}"


def test_apply_scores_sorts_descending():
    events = [
        _make_event("Senior Bingo"),
        _make_event("EDM Nightclub Rave", ["nightclub", "edm", "rave"]),
        _make_event("Happy Hour Rooftop", ["happy-hour", "rooftop"]),
    ]
    profile = UserProfile(age=25)
    scored = apply_age_scores(events, profile)
    assert scored[0].age_score >= scored[-1].age_score


def test_age_bracket_mapping():
    assert AgeBracket.from_age(18) == AgeBracket.UNDER_21
    assert AgeBracket.from_age(25) == AgeBracket.TWENTIES
    assert AgeBracket.from_age(35) == AgeBracket.THIRTIES
    assert AgeBracket.from_age(45) == AgeBracket.FORTIES
    assert AgeBracket.from_age(60) == AgeBracket.FIFTIES_PLUS


if __name__ == "__main__":
    test_twenties_boost_nightclub()
    test_twenties_penalize_senior()
    test_fifties_boost_jazz()
    test_under_21_penalize_cocktail()
    test_apply_scores_sorts_descending()
    test_age_bracket_mapping()
    print("All tests passed!")
