"""
Google Places — venue discovery and reviews for the knowledge graph.
Docs: https://developers.google.com/maps/documentation/places/web-service
"""
from __future__ import annotations

import httpx
import structlog
from app.config import settings
from models.user_profile import Event
from sources.base import EventSource

log = structlog.get_logger()


class GooglePlacesClient(EventSource):
    name = "google_places"

    BASE_URL = "https://maps.googleapis.com/maps/api/place"

    async def fetch_events(
        self,
        city: str,
        date: str,
        *,
        query: str = "",
        limit: int = 25,
    ) -> list[Event]:
        """
        Google Places doesn't have 'events' per se — we use it
        to find venues (bars, clubs, restaurants) and pull reviews
        to feed into Cognee's knowledge graph.
        """
        if not settings.google_places_api_key:
            log.warning("google_places.no_api_key", msg="Skipping Google Places — no API key set")
            return []

        search_query = query or f"nightlife bars clubs {city}"

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/textsearch/json",
                    params={
                        "query": search_query,
                        "key": settings.google_places_api_key,
                    },
                )
                resp.raise_for_status()
                data = resp.json()

            events = []
            for place in data.get("results", [])[:limit]:
                loc = place.get("geometry", {}).get("location", {})
                events.append(Event(
                    id=place.get("place_id", ""),
                    title=place.get("name", ""),
                    description=place.get("formatted_address", ""),
                    source=self.name,
                    venue_name=place.get("name", ""),
                    venue_address=place.get("formatted_address", ""),
                    latitude=loc.get("lat"),
                    longitude=loc.get("lng"),
                    tags=place.get("types", []),
                    price=_price_level(place.get("price_level")),
                ))
            return events

        except Exception as exc:
            log.error("google_places.fetch_error", error=str(exc))
            return []

    async def fetch_reviews(self, place_id: str) -> list[dict]:
        """Fetch reviews for a specific place — these go into Cognee."""
        if not settings.google_places_api_key:
            return []

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/details/json",
                    params={
                        "place_id": place_id,
                        "fields": "name,reviews,rating,user_ratings_total",
                        "key": settings.google_places_api_key,
                    },
                )
                resp.raise_for_status()
                result = resp.json().get("result", {})
            return result.get("reviews", [])
        except Exception as exc:
            log.error("google_places.reviews_error", place_id=place_id, error=str(exc))
            return []


def _price_level(level: int | None) -> str:
    return {0: "Free", 1: "$", 2: "$$", 3: "$$$", 4: "$$$$"}.get(level or 0, "")
