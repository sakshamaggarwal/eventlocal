"""
Eventbrite event source.
Docs: https://www.eventbrite.com/platform/api
"""
from __future__ import annotations

import httpx
import structlog
from app.config import settings
from models.user_profile import Event
from sources.base import EventSource

log = structlog.get_logger()


class EventbriteClient(EventSource):
    name = "eventbrite"

    BASE_URL = "https://www.eventbriteapi.com/v3"

    async def fetch_events(
        self,
        city: str,
        date: str,
        *,
        query: str = "",
        limit: int = 25,
    ) -> list[Event]:
        """Fetch events from Eventbrite's API."""
        if not settings.eventbrite_api_key:
            log.warning("eventbrite.no_api_key", msg="Skipping Eventbrite — no API key set")
            return []

        headers = {"Authorization": f"Bearer {settings.eventbrite_api_key}"}

        # Map city names to Eventbrite location params
        location_map = {
            "bay-area": {"location.address": "San Francisco, CA", "location.within": "50mi"},
            "seattle": {"location.address": "Seattle, WA", "location.within": "25mi"},
        }
        loc_params = location_map.get(city, {"location.address": city, "location.within": "25mi"})

        params = {
            **loc_params,
            "start_date.keyword": date or "today",
            "page_size": min(limit, 50),
            "expand": "venue",
        }
        if query:
            params["q"] = query

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/events/search/",
                    headers=headers,
                    params=params,
                )
                resp.raise_for_status()
                data = resp.json()

            events = []
            for ev in data.get("events", []):
                venue = ev.get("venue", {}) or {}
                addr = venue.get("address", {}) or {}
                events.append(Event(
                    id=ev.get("id", ""),
                    title=ev.get("name", {}).get("text", "Untitled"),
                    description=ev.get("description", {}).get("text", "")[:500],
                    source=self.name,
                    url=ev.get("url", ""),
                    venue_name=venue.get("name", ""),
                    venue_address=addr.get("localized_address_display", ""),
                    latitude=float(addr["latitude"]) if addr.get("latitude") else None,
                    longitude=float(addr["longitude"]) if addr.get("longitude") else None,
                    start_time=ev.get("start", {}).get("utc", ""),
                    end_time=ev.get("end", {}).get("utc", ""),
                    price="Free" if ev.get("is_free") else "",
                    image_url=ev.get("logo", {}).get("url", "") if ev.get("logo") else "",
                ))
            return events

        except Exception as exc:
            log.error("eventbrite.fetch_error", error=str(exc))
            return []
