"""
Personalization layers — scores events 0-1 based on age bracket and social mode.

Two independent scores are computed and blended via composite_score on the Event model.
"""
from __future__ import annotations

from config import (
    AGE_SIGNALS,
    SOCIAL_SIGNALS,
    SCORING_BASE,
    SCORING_BOOST,
    SCORING_PENALIZE,
)
from models.user_profile import AgeBracket, Event, UserProfile


_AGE_SIGNALS: dict[AgeBracket, dict] = {
    AgeBracket.from_age({"under_21": 18, "21_29": 25, "30_39": 35, "40_49": 45, "50_plus": 55}[k]): v
    for k, v in AGE_SIGNALS.items()
}


def _keyword_score(text: str, signals: dict) -> float:
    score = SCORING_BASE
    for keyword in signals.get("boost", []):
        if keyword in text:
            score += SCORING_BOOST
    for keyword in signals.get("penalize", []):
        if keyword in text:
            score -= SCORING_PENALIZE
    return max(0.0, min(1.0, round(score, 2)))


def _searchable_text(event: Event) -> str:
    return " ".join([
        event.title.lower(),
        event.description.lower(),
        " ".join(t.lower() for t in event.tags),
    ])


def score_event(event: Event, profile: UserProfile) -> float:
    """Return a 0-1 age-fit score for an event."""
    signals = _AGE_SIGNALS.get(profile.age_bracket, {"boost": [], "penalize": []})
    return _keyword_score(_searchable_text(event), signals)


def score_social(event: Event, profile: UserProfile) -> float:
    """Return a 0-1 social-mode-fit score for an event."""
    signals = SOCIAL_SIGNALS.get(profile.social_mode, {"boost": [], "penalize": []})
    return _keyword_score(_searchable_text(event), signals)


def apply_age_scores(events: list[Event], profile: UserProfile) -> list[Event]:
    """Score all events by age + social mode and sort by composite_score descending."""
    for event in events:
        event.age_score = score_event(event, profile)
        event.social_score = score_social(event, profile)
    return sorted(events, key=lambda e: e.composite_score, reverse=True)
