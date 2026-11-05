"""
Proprietary configuration loader.

Tries to load tuned values from config/proprietary.py (gitignored).
Falls back to config/proprietary_defaults.py (generic stubs in repo).
"""
try:
    from config.proprietary import (
        AGE_SIGNALS,
        SCORING_BASE,
        SCORING_BOOST,
        SCORING_PENALIZE,
        KB_USER_WEIGHT,
        KB_GLOBAL_WEIGHT,
        FEEDBACK_CHOSEN_WEIGHT,
        FEEDBACK_RATED_MULTIPLIER,
        FEEDBACK_SKIPPED_WEIGHT,
        ONTOLOGY_EXTRACTION_PROMPT,
        QUERY_TEMPLATES,
    )
    PROPRIETARY_LOADED = True
except ImportError:
    from config.proprietary_defaults import (
        AGE_SIGNALS,
        SCORING_BASE,
        SCORING_BOOST,
        SCORING_PENALIZE,
        KB_USER_WEIGHT,
        KB_GLOBAL_WEIGHT,
        FEEDBACK_CHOSEN_WEIGHT,
        FEEDBACK_RATED_MULTIPLIER,
        FEEDBACK_SKIPPED_WEIGHT,
        ONTOLOGY_EXTRACTION_PROMPT,
        QUERY_TEMPLATES,
    )
    PROPRIETARY_LOADED = False

__all__ = [
    "AGE_SIGNALS",
    "SCORING_BASE",
    "SCORING_BOOST",
    "SCORING_PENALIZE",
    "KB_USER_WEIGHT",
    "KB_GLOBAL_WEIGHT",
    "FEEDBACK_CHOSEN_WEIGHT",
    "FEEDBACK_RATED_MULTIPLIER",
    "FEEDBACK_SKIPPED_WEIGHT",
    "ONTOLOGY_EXTRACTION_PROMPT",
    "QUERY_TEMPLATES",
    "PROPRIETARY_LOADED",
]
