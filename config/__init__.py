"""
Proprietary configuration loader.

Load order (per key, with fallback):
1. config/proprietary.py (gitignored local file)
2. Streamlit secrets  (st.secrets["proprietary"] on Streamlit Cloud)
3. config/proprietary_defaults.py (generic stubs in repo)

New keys added to defaults are always available even if the proprietary
file predates them — defaults load first, then proprietary overlays.
"""
from __future__ import annotations

import json

_ALL_KEYS = [
    "AGE_SIGNALS",
    "SOCIAL_SIGNALS",
    "SOCIAL_WEIGHT",
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
]

PROPRIETARY_LOADED = False


def _load_defaults() -> dict:
    from config import proprietary_defaults as d
    return {k: getattr(d, k) for k in _ALL_KEYS}


def _try_proprietary_file() -> dict | None:
    try:
        from config import proprietary  # noqa: F811
        vals = {}
        found_any = False
        for k in _ALL_KEYS:
            if hasattr(proprietary, k):
                vals[k] = getattr(proprietary, k)
                found_any = True
        return vals if found_any else None
    except ImportError:
        return None


def _try_streamlit_secrets() -> dict | None:
    try:
        import streamlit as st
        sec = st.secrets.get("proprietary")
        if sec is None:
            return None
        vals = {}
        found_any = False
        for k in _ALL_KEYS:
            raw = sec.get(k)
            if raw is None:
                continue
            found_any = True
            if isinstance(raw, str) and raw.lstrip().startswith(("{", "[")):
                vals[k] = json.loads(raw)
            else:
                vals[k] = raw
        return vals if found_any else None
    except Exception:
        return None


# Start with defaults, overlay proprietary/secrets on top
_loaded = _load_defaults()

_overlay = _try_proprietary_file()
if _overlay is not None:
    _loaded.update(_overlay)
    PROPRIETARY_LOADED = True
else:
    _overlay = _try_streamlit_secrets()
    if _overlay is not None:
        _loaded.update(_overlay)
        PROPRIETARY_LOADED = True

AGE_SIGNALS = _loaded["AGE_SIGNALS"]
SOCIAL_SIGNALS = _loaded["SOCIAL_SIGNALS"]
SOCIAL_WEIGHT = _loaded["SOCIAL_WEIGHT"]
SCORING_BASE = _loaded["SCORING_BASE"]
SCORING_BOOST = _loaded["SCORING_BOOST"]
SCORING_PENALIZE = _loaded["SCORING_PENALIZE"]
KB_USER_WEIGHT = _loaded["KB_USER_WEIGHT"]
KB_GLOBAL_WEIGHT = _loaded["KB_GLOBAL_WEIGHT"]
FEEDBACK_CHOSEN_WEIGHT = _loaded["FEEDBACK_CHOSEN_WEIGHT"]
FEEDBACK_RATED_MULTIPLIER = _loaded["FEEDBACK_RATED_MULTIPLIER"]
FEEDBACK_SKIPPED_WEIGHT = _loaded["FEEDBACK_SKIPPED_WEIGHT"]
ONTOLOGY_EXTRACTION_PROMPT = _loaded["ONTOLOGY_EXTRACTION_PROMPT"]
QUERY_TEMPLATES = _loaded["QUERY_TEMPLATES"]

__all__ = [*_ALL_KEYS, "PROPRIETARY_LOADED"]
