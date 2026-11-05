"""
Proprietary configuration loader.

Load order:
1. config/proprietary.py (gitignored local file)
2. Streamlit secrets  (st.secrets["proprietary"] on Streamlit Cloud)
3. config/proprietary_defaults.py (generic stubs in repo)
"""
from __future__ import annotations

import json

_ALL_KEYS = [
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
]

PROPRIETARY_LOADED = False


def _try_proprietary_file() -> dict | None:
    try:
        from config import proprietary  # noqa: F811
        return {k: getattr(proprietary, k) for k in _ALL_KEYS}
    except ImportError:
        return None


def _try_streamlit_secrets() -> dict | None:
    try:
        import streamlit as st
        sec = st.secrets.get("proprietary")
        if sec is None:
            return None
        vals = {}
        for k in _ALL_KEYS:
            raw = sec.get(k)
            if raw is None:
                return None
            if isinstance(raw, str) and raw.lstrip().startswith(("{", "[")):
                vals[k] = json.loads(raw)
            else:
                vals[k] = raw
        return vals
    except Exception:
        return None


def _load_defaults() -> dict:
    from config import proprietary_defaults as d
    return {k: getattr(d, k) for k in _ALL_KEYS}


_loaded = _try_proprietary_file()
if _loaded is not None:
    PROPRIETARY_LOADED = True
else:
    _loaded = _try_streamlit_secrets()
    if _loaded is not None:
        PROPRIETARY_LOADED = True
    else:
        _loaded = _load_defaults()

AGE_SIGNALS = _loaded["AGE_SIGNALS"]
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
