"""
Prompt loader — reads system-prompt.md and makes it available to agents.
"""
from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SYSTEM_PROMPT_PATH = _ROOT / "system-prompt.md"

_cached_prompt: str | None = None


_EXAMPLE_PATH = _ROOT / "system-prompt.example.md"


def load_system_prompt() -> str:
    """Load the Event Concierge system prompt, falling back to the example."""
    global _cached_prompt
    if _cached_prompt is None:
        if _SYSTEM_PROMPT_PATH.exists():
            _cached_prompt = _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
        elif _EXAMPLE_PATH.exists():
            _cached_prompt = _EXAMPLE_PATH.read_text(encoding="utf-8")
        else:
            _cached_prompt = "You are an event discovery assistant for the Bay Area."
    return _cached_prompt
