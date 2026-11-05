"""
Prompt loader — reads system-prompt.md and makes it available to agents.

Load order:
1. system-prompt.md (gitignored local file)
2. Streamlit secrets  (st.secrets["system_prompt"])
3. system-prompt.example.md (placeholder in repo)
4. Inline default
"""
from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SYSTEM_PROMPT_PATH = _ROOT / "system-prompt.md"
_EXAMPLE_PATH = _ROOT / "system-prompt.example.md"

_cached_prompt: str | None = None


def load_system_prompt() -> str:
    """Load the Event Concierge system prompt, with fallback chain."""
    global _cached_prompt
    if _cached_prompt is None:
        if _SYSTEM_PROMPT_PATH.exists():
            _cached_prompt = _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
        else:
            _cached_prompt = _try_streamlit_secrets()
            if _cached_prompt is None:
                if _EXAMPLE_PATH.exists():
                    _cached_prompt = _EXAMPLE_PATH.read_text(encoding="utf-8")
                else:
                    _cached_prompt = "You are an event discovery assistant for the Bay Area."
    return _cached_prompt


def _try_streamlit_secrets() -> str | None:
    try:
        import streamlit as st
        prompt = st.secrets.get("system_prompt")
        if prompt and isinstance(prompt, str) and len(prompt) > 50:
            return prompt
    except Exception:
        pass
    return None
