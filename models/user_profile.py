"""
Pydantic models for user input and event data.
"""
from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Age brackets — the single personalization layer for Hackathon MVP
# ---------------------------------------------------------------------------

class AgeBracket(str, Enum):
    """Age brackets mapped to the slider in the UI."""
    UNDER_21 = "under_21"
    TWENTIES = "21_29"
    THIRTIES = "30_39"
    FORTIES  = "40_49"
    FIFTIES_PLUS = "50_plus"

    @classmethod
    def from_age(cls, age: int) -> "AgeBracket":
        if age < 21:
            return cls.UNDER_21
        elif age < 30:
            return cls.TWENTIES
        elif age < 40:
            return cls.THIRTIES
        elif age < 50:
            return cls.FORTIES
        else:
            return cls.FIFTIES_PLUS


class UserProfile(BaseModel):
    """User profile for personalization — MVP has age only."""

    # --- MVP (Hackathon) ---
    age: int = Field(ge=13, le=100, description="User's age")

    # --- MVP social mode toggle ---
    social_mode: str = "solo"  # "solo", "group", or "date"

    # --- Post-hackathon layers (kept as placeholders) ---
    is_local: bool | None = None         # local vs traveling
    wants_networking: bool | None = None  # networking vs party
    cultural_affinity: str | None = None  # e.g. "desi", "latin", "kpop"

    @property
    def age_bracket(self) -> AgeBracket:
        return AgeBracket.from_age(self.age)


# ---------------------------------------------------------------------------
# Event model
# ---------------------------------------------------------------------------

class Event(BaseModel):
    """Normalized event from any source."""

    id: str
    title: str
    description: str = ""
    source: str                # "luma", "eventbrite", "google_places"
    url: str = ""
    venue_name: str = ""
    venue_address: str = ""
    latitude: float | None = None
    longitude: float | None = None
    start_time: str = ""       # ISO 8601
    end_time: str = ""
    price: str = ""            # "Free", "$10", "$20-50"
    tags: list[str] = Field(default_factory=list)
    image_url: str = ""
    rsvp_count: int | None = None

    # Personalization scores (filled by layers)
    age_score: float = 0.0     # 0-1

    @property
    def composite_score(self) -> float:
        """Weighted blend of all layer scores. MVP: age only."""
        # TODO: add weights config once more layers exist
        return self.age_score


class EveningPlan(BaseModel):
    """A generated evening itinerary."""

    city: str
    date: str
    user_profile: UserProfile
    events: list[Event]
    itinerary_markdown: str = ""
    explanation: str = ""
