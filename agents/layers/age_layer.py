"""
Age personalization layer — scores events 0-1 based on age bracket fit.

This is the ONLY layer used in the Hackathon MVP.
"""
from __future__ import annotations

from models.user_profile import AgeBracket, Event, UserProfile


# Keywords / tags that signal age affinity
_AGE_SIGNALS: dict[AgeBracket, dict] = {
    AgeBracket.UNDER_21: {
        "boost": ["all-ages", "teen", "anime", "gaming", "esports", "boba", "college"],
        "penalize": ["wine-tasting", "cocktail-lounge", "networking", "executive"],
    },
    AgeBracket.TWENTIES: {
        "boost": ["nightclub", "edm", "rave", "brunch", "rooftop", "dating", "happy-hour",
                   "tech-meetup", "startup", "hackathon", "bar-crawl"],
        "penalize": ["senior", "retirement", "kids", "family"],
    },
    AgeBracket.THIRTIES: {
        "boost": ["cocktail", "wine-bar", "networking", "live-music", "jazz", "comedy",
                   "supper-club", "speakeasy", "rooftop", "craft-beer"],
        "penalize": ["teen", "all-ages", "kids"],
    },
    AgeBracket.FORTIES: {
        "boost": ["wine-tasting", "jazz", "theater", "fine-dining", "live-music",
                   "gallery", "charity-gala", "golf"],
        "penalize": ["rave", "edm", "teen", "college"],
    },
    AgeBracket.FIFTIES_PLUS: {
        "boost": ["classical", "jazz", "theater", "wine-tasting", "garden-party",
                   "museum", "opera", "cruise"],
        "penalize": ["rave", "edm", "nightclub", "bar-crawl"],
    },
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

    score = 0.5

    for keyword in signals["boost"]:
        if keyword in text:
            score += 0.1

    for keyword in signals["penalize"]:
        if keyword in text:
            score -= 0.1

    return max(0.0, min(1.0, round(score, 2)))


def apply_age_scores(events: list[Event], profile: UserProfile) -> list[Event]:
    """Score all events and sort by age_score descending."""
    for event in events:
        event.age_score = score_event(event, profile)
    return sorted(events, key=lambda e: e.age_score, reverse=True)
