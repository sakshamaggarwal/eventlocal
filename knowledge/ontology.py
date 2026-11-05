"""
Custom ontology for the eventlocal Event Brain.

Defines domain-specific entity types, relationship types, and multi-hop
query templates that tell Cognee exactly what to extract and how to
relate entities — instead of guessing from raw text.

4 entity types  · 15 named relationships · 6 multi-hop query templates
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


# ---------------------------------------------------------------------------
# Entity types
# ---------------------------------------------------------------------------

@dataclass
class EventEntity:
    """An event happening at a specific time and place."""
    name: str = ""
    event_type: str = ""           # concert, meetup, party, workshop, etc.
    start_time: str = ""           # ISO 8601
    end_time: str = ""
    price_range: str = ""          # "Free", "$10-20", "$50+"
    vibes: list[str] = field(default_factory=list)       # chill, rowdy, intimate, electric
    crowd_type: str = ""           # young-professionals, families, students, mixed
    group_size: str = ""           # solo-friendly, couples, small-group, large-group
    noise_level: str = ""          # quiet, moderate, loud
    formality: str = ""            # casual, smart-casual, formal
    age_appeal: str = ""           # under-21, 20s, 30s, 40s, 50+, all-ages
    tags: list[str] = field(default_factory=list)


@dataclass
class VenueEntity:
    """A physical location where events take place."""
    name: str = ""
    venue_type: str = ""           # bar, club, restaurant, park, gallery, theater
    neighborhood: str = ""
    address: str = ""
    latitude: float = 0.0
    longitude: float = 0.0
    capacity: str = ""             # intimate(<50), medium(50-200), large(200+)
    ambiance: list[str] = field(default_factory=list)    # cozy, trendy, upscale, dive
    noise_level: str = ""
    price_tier: str = ""           # $, $$, $$$, $$$$
    parking: str = ""              # easy, street, valet, none
    transit_friendly: bool = False
    outdoor_space: bool = False


@dataclass
class ReviewEntity:
    """A user review of a venue or event."""
    text: str = ""
    rating: float = 0.0            # 0-5
    source: str = ""               # google, yelp, user-submitted
    date: str = ""
    sentiment: str = ""            # positive, neutral, negative
    mentioned_vibes: list[str] = field(default_factory=list)
    mentioned_crowd: str = ""
    recommended_for: str = ""      # dates, groups, solo, networking
    noise_comment: str = ""
    wait_time: str = ""            # none, short, long


@dataclass
class PatternEntity:
    """A learned pattern about venue/event behavior over time."""
    pattern_type: str = ""         # crowd-shift, popularity-trend, seasonal
    description: str = ""
    confidence: float = 0.0        # 0-1
    time_range: str = ""           # weekday-evening, weekend-night, etc.
    demographic_shift: str = ""    # "20s → 30s crowd after 10pm"
    peak_times: list[str] = field(default_factory=list)
    related_events: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Relationship types (15 named edges)
# ---------------------------------------------------------------------------

class Relationship(str, Enum):
    """Named edges in the Event Brain knowledge graph."""
    HOSTED_AT = "hosted_at"                 # Event → Venue
    REVIEW_OF = "review_of"                 # Review → Venue or Event
    SIMILAR_CROWD = "similar_crowd"         # Venue ↔ Venue
    APPEALS_TO_AGE = "appeals_to_age"       # Event/Venue → AgeBracket
    BEST_FOR_GROUP = "best_for_group"       # Venue → GroupSize
    SAME_NIGHT = "same_night"               # Event ↔ Event (same date)
    NEARBY = "nearby"                       # Venue ↔ Venue (walkable)
    FOLLOWED_BY = "followed_by"             # Event → Event (good sequence)
    HAS_PATTERN = "has_pattern"             # Venue → Pattern
    SIMILAR_VIBE = "similar_vibe"           # Event ↔ Event
    RECOMMENDED_WITH = "recommended_with"   # Event → Event (co-recommended)
    POPULAR_AMONG = "popular_among"         # Venue → Demographic
    REVIEWED_BY = "reviewed_by"             # Venue → Review
    IN_NEIGHBORHOOD = "in_neighborhood"     # Venue → Neighborhood
    COMPETES_WITH = "competes_with"         # Event ↔ Event (similar time/type)


# ---------------------------------------------------------------------------
# Multi-hop query templates (6 templates)
# ---------------------------------------------------------------------------

MULTI_HOP_TEMPLATES: dict[str, str] = {
    "age_personalized": (
        "Find events → hosted_at → venues → that have reviews → "
        "mentioning '{age_bracket}' crowd or '{age_appeal}' vibes. "
        "Rank by review sentiment and age-bracket match."
    ),
    "solo_friendly": (
        "Find events → hosted_at → venues → with reviews → "
        "recommending 'solo' visits → in neighborhoods → "
        "that are transit-friendly. Prefer moderate noise, casual formality."
    ),
    "date_night": (
        "Find events → hosted_at → venues → with reviews → "
        "mentioning 'dates' or 'romantic' → nearby → restaurants → "
        "with $$+ price tier. Build a sequence via followed_by."
    ),
    "group_outing": (
        "Find events → best_for_group 'large-group' → hosted_at → "
        "venues → with capacity 'medium' or 'large' → "
        "same_night as other group-friendly events."
    ),
    "hidden_gems": (
        "Find venues → with reviews → rating >= 4.0 → "
        "but low event count → has_pattern 'popularity-trend' rising → "
        "in neighborhoods with nearby transit."
    ),
    "neighborhood_crawl": (
        "Find venues → in_neighborhood '{neighborhood}' → "
        "nearby → other venues → with events → same_night → "
        "build followed_by chain ordered by start_time."
    ),
}


def get_query_template(template_name: str, **kwargs: str) -> str:
    """Return a formatted multi-hop query template."""
    template = MULTI_HOP_TEMPLATES.get(template_name, "")
    if not template:
        return ""
    try:
        return template.format(**kwargs)
    except KeyError:
        return template


# ---------------------------------------------------------------------------
# Ontology prompt — tells Cognee what to extract
# ---------------------------------------------------------------------------

ONTOLOGY_PROMPT = """\
You are extracting structured knowledge from event listings, venue \
descriptions, and user reviews for a city's event ecosystem.

## Entity Types to Extract

1. **EventEntity**: name, event_type, start_time, end_time, price_range, \
vibes (list), crowd_type, group_size, noise_level, formality, age_appeal, tags
2. **VenueEntity**: name, venue_type, neighborhood, address, capacity, \
ambiance (list), noise_level, price_tier, transit_friendly, outdoor_space
3. **ReviewEntity**: text, rating, source, sentiment, mentioned_vibes (list), \
mentioned_crowd, recommended_for, noise_comment, wait_time
4. **PatternEntity**: pattern_type, description, confidence, time_range, \
demographic_shift, peak_times (list)

## Relationship Types to Identify

- hosted_at: Event → Venue
- review_of: Review → Venue or Event
- similar_crowd: Venue ↔ Venue (same demographic)
- appeals_to_age: Event/Venue → age bracket (under-21, 20s, 30s, 40s, 50+)
- best_for_group: Venue → group size (solo, couples, small-group, large-group)
- same_night: Event ↔ Event (happening the same evening)
- nearby: Venue ↔ Venue (within walking distance, ~15 min)
- followed_by: Event → Event (good evening sequence)
- has_pattern: Venue → Pattern (observed behavioral pattern)
- similar_vibe: Event ↔ Event (matching vibes/ambiance)
- recommended_with: Event → Event (often co-recommended)
- popular_among: Venue → demographic group
- reviewed_by: Venue → Review
- in_neighborhood: Venue → neighborhood name
- competes_with: Event ↔ Event (similar time slot and type)

## Extraction Guidelines

- Infer vibes from descriptive language ("electric atmosphere" → "electric")
- Infer age_appeal from context ("craft cocktail lounge" → "30s", \
"all-ages show" → "under-21, all-ages")
- Mark crowd_type from review mentions ("lots of tech bros" → "young-professionals")
- Identify patterns from multiple reviews of the same venue
- Create nearby relationships for venues in the same neighborhood
- Create same_night relationships for events on the same date
"""


# ---------------------------------------------------------------------------
# Helpers for the engine
# ---------------------------------------------------------------------------

ALL_ENTITY_TYPES = [EventEntity, VenueEntity, ReviewEntity, PatternEntity]
ALL_RELATIONSHIPS = list(Relationship)
