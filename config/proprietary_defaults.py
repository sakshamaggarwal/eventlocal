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
# Social mode personalization signals
# ---------------------------------------------------------------------------

SOCIAL_SIGNALS: dict[str, dict] = {
    "solo": {
        "boost": ["jazz", "museum", "cafe", "gallery", "workshop", "comedy", "reading", "meditation", "quiet", "bar"],
        "penalize": ["group", "couples", "team", "family", "party"],
    },
    "group": {
        "boost": ["bar-crawl", "party", "group", "dance", "nightclub", "rooftop", "trivia", "karaoke", "festival", "concert", "beer", "sports"],
        "penalize": ["intimate", "quiet", "solo", "meditation", "romantic"],
    },
    "date": {
        "boost": ["cocktail", "speakeasy", "rooftop", "jazz", "wine-bar", "romantic", "intimate", "dinner", "sunset", "live-music", "lounge"],
        "penalize": ["loud", "crowded", "family", "kids", "gaming", "esports", "sports-bar"],
    },
}

SOCIAL_WEIGHT = 0.3

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

# ---------------------------------------------------------------------------
# Planner system prompt (generic placeholder)
# ---------------------------------------------------------------------------

PLANNER_SYSTEM_PROMPT = """\
You are an evening-outing planner for {city}.

Given a list of scored events, build a personalized evening plan
with 2-4 stops. Tailor suggestions to the user's age bracket ({age_bracket}).
Return your plan as markdown with emoji headers.
"""

# ---------------------------------------------------------------------------
# Cognee query bracket descriptions (generic placeholders)
# ---------------------------------------------------------------------------

COGNEE_BRACKET_DESCRIPTIONS: dict[str, str] = {
    "under_21": "under 21",
    "21_29": "in their twenties",
    "30_39": "in their thirties",
    "40_49": "in their forties",
    "50_plus": "over 50",
}
