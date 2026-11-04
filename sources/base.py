"""
Abstract base for all event sources.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from models.user_profile import Event


class EventSource(ABC):
    """Every event source implements this interface."""

    name: str = "unknown"

    @abstractmethod
    async def fetch_events(
        self,
        city: str,
        date: str,
        *,
        query: str = "",
        limit: int = 25,
    ) -> list[Event]:
        """Return normalized Event objects for a city + date."""
        ...
