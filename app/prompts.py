"""
Prompt loader — reads system-prompt.md and makes it available to agents.
"""
from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SYSTEM_PROMPT_PATH = _ROOT / "system-prompt.md"

_cached_prompt: str | None = None


def load_system_prompt() -> str:
    """Load the Event Concierge system prompt from system-prompt.md."""
    global _cached_prompt
    if _cached_prompt is None:
        _cached_prompt = _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    return _cached_prompt
