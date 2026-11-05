"""
Generic default values — shipped in the public repo.

These make the app runnable but lack the tuned parameters.
Place your tuned values in config/proprietary.py (gitignored).
"""

# ---------------------------------------------------------------------------
# Age personalization signals (generic placeholders)
# ---------------------------------------------------------------------------

AGE_SIGNALS: dict[str, dict] = {
    "under_21": {
        "boost": ["all-ages", "gaming"],
        "penalize": ["wine-tasting"],
    },
    "21_29": {
        "boost": ["nightclub", "rooftop"],
        "penalize": ["senior"],
    },
    "30_39": {
        "boost": ["cocktail", "live-music"],
        "penalize": ["teen"],
    },
    "40_49": {
        "boost": ["jazz", "theater"],
        "penalize": ["rave"],
    },
    "50_plus": {
        "boost": ["classical", "jazz"],
        "penalize": ["nightclub"],
    },
}

# ---------------------------------------------------------------------------
# Scoring weights (generic)
# ---------------------------------------------------------------------------

SCORING_BASE = 0.5
SCORING_BOOST = 0.1
SCORING_PENALIZE = 0.1

# ---------------------------------------------------------------------------
# Knowledge-base merge weights (generic)
# ---------------------------------------------------------------------------

KB_USER_WEIGHT = 1.5
KB_GLOBAL_WEIGHT = 1.0

# ---------------------------------------------------------------------------
# Feedback loop weights (generic)
# ---------------------------------------------------------------------------

FEEDBACK_CHOSEN_WEIGHT = 0.1
FEEDBACK_RATED_MULTIPLIER = 0.05
FEEDBACK_SKIPPED_WEIGHT = -0.05

# ---------------------------------------------------------------------------
# Ontology extraction prompt (generic placeholder)
# ---------------------------------------------------------------------------

ONTOLOGY_EXTRACTION_PROMPT = """\
Extract structured knowledge from event listings and venue descriptions.

## Entity Types
1. EventEntity: name, event_type, start_time, end_time, price_range, tags
2. VenueEntity: name, venue_type, neighborhood, address
3. ReviewEntity: text, rating, source, sentiment
4. PatternEntity: pattern_type, description, confidence

## Relationships
- hosted_at, review_of, similar_crowd, appeals_to_age, nearby, same_night
"""

# ---------------------------------------------------------------------------
# Multi-hop query templates (generic placeholders)
# ---------------------------------------------------------------------------

QUERY_TEMPLATES: dict[str, str] = {
    "age_personalized": (
        "Find events for '{age_bracket}' age group, ranked by relevance."
    ),
    "solo_friendly": (
        "Find solo-friendly events at transit-accessible venues."
    ),
    "date_night": (
        "Find date-night events near good restaurants."
    ),
    "group_outing": (
        "Find group-friendly events at large venues."
    ),
    "hidden_gems": (
        "Find highly-rated but lesser-known venues with rising popularity."
    ),
    "neighborhood_crawl": (
        "Find nearby venues in '{neighborhood}' for a crawl."
    ),
}
