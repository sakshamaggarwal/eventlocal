"""
Age personalization layer — scores events 0-1 based on age bracket fit.

This is the ONLY layer used in the Hackathon MVP.
"""
from __future__ import annotations

from config import AGE_SIGNALS, SCORING_BASE, SCORING_BOOST, SCORING_PENALIZE
from models.user_profile import AgeBracket, Event, UserProfile


_AGE_SIGNALS: dict[AgeBracket, dict] = {
    AgeBracket.from_age({"under_21": 18, "21_29": 25, "30_39": 35, "40_49": 45, "50_plus": 55}[k]): v
    for k, v in AGE_SIGNALS.items()
}


def score_event(event: Event, profile: UserProfile) -> float:
    """
    Return a 0-1 age-fit score for an event.

    Strategy:
    - Start at 0.5 (neutral)
    - +0.1 per matching boost keyword (cap at 1.0)
    - -0.1 per matching penalize keyword (floor at 0.0)
    - Match against event tags + title + description
    """
    bracket = profile.age_bracket
    signals = _AGE_SIGNALS.get(bracket, {"boost": [], "penalize": []})

    # Build searchable text
    text = " ".join([
        event.title.lower(),
        event.description.lower(),
        " ".join(t.lower() for t in event.tags),
    ])

    score = SCORING_BASE

    for keyword in signals["boost"]:
        if keyword in text:
            score += SCORING_BOOST

    for keyword in signals["penalize"]:
        if keyword in text:
            score -= SCORING_PENALIZE

    return max(0.0, min(1.0, round(score, 2)))


def apply_age_scores(events: list[Event], profile: UserProfile) -> list[Event]:
    """Score all events and sort by age_score descending."""
    for event in events:
        event.age_score = score_event(event, profile)
    return sorted(events, key=lambda e: e.age_score, reverse=True)
