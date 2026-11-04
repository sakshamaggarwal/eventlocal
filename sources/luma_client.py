"""
Luma event source.
Docs: https://docs.lu.ma/reference/
"""
from __future__ import annotations

import httpx
import structlog
from app.config import settings
from models.user_profile import Event
from sources.base import EventSource

log = structlog.get_logger()


class LumaClient(EventSource):
    name = "luma"

    BASE_URL = "https://api.lu.ma/public/v2"

    async def fetch_events(
        self,
        city: str,
        date: str,
        *,
        query: str = "",
        limit: int = 25,
    ) -> list[Event]:
        """Fetch events from Luma's public API."""
        if not settings.luma_api_key:
            log.warning("luma.no_api_key", msg="Skipping Luma — no API key set")
            return []

        headers = {"x-luma-api-key": settings.luma_api_key}
        params: dict = {
            "pagination_limit": min(limit, 50),
        }

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                # Discover events via search or listing
                resp = await client.get(
                    f"{self.BASE_URL}/event/search",
                    headers=headers,
                    params={**params, "query": query or city},
                )
                resp.raise_for_status()
                data = resp.json()

            events = []
            for entry in data.get("entries", []):
                ev = entry.get("event", {})
                events.append(Event(
                    id=ev.get("api_id", ""),
                    title=ev.get("name", "Untitled"),
                    description=ev.get("description_short", ""),
                    source=self.name,
                    url=ev.get("url", ""),
                    venue_name=ev.get("geo_address_info", {}).get("place_name", ""),
                    venue_address=ev.get("geo_address_info", {}).get("full_address", ""),
                    latitude=ev.get("geo_latitude"),
                    longitude=ev.get("geo_longitude"),
                    start_time=ev.get("start_at", ""),
                    end_time=ev.get("end_at", ""),
                    tags=[t.get("name", "") for t in ev.get("tags", [])],
                    image_url=ev.get("cover_url", ""),
                ))
            return events

        except Exception as exc:
            log.error("luma.fetch_error", error=str(exc))
            return []
