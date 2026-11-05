"""
SeatGeek API — concerts, sports, comedy, theater.
Docs: https://platform.seatgeek.com/
Free tier: register for a client_id, no hard daily limit.
"""
from __future__ import annotations

import structlog
from app.config import settings
from models.user_profile import Event
from sources.base import EventSource
from sources.http_utils import fetch_with_retry

log = structlog.get_logger()

CITY_COORDS = {
    "bay-area": (37.7749, -122.4194),
    "seattle": (47.6062, -122.3321),
    "los-angeles": (34.0522, -118.2437),
    "new-york": (40.7128, -74.0060),
}


class SeatGeekClient(EventSource):
    name = "seatgeek"

    BASE_URL = "https://api.seatgeek.com/2"

    async def fetch_events(
        self,
        city: str,
        date: str,
        *,
        query: str = "",
        limit: int = 25,
    ) -> list[Event]:
        if not settings.seatgeek_client_id:
            log.warning("seatgeek.no_client_id", msg="Skipping SeatGeek — no client_id set")
            return []

        coords = CITY_COORDS.get(city)
        params: dict = {
            "client_id": settings.seatgeek_client_id,
            "per_page": min(limit, 50),
            "sort": "score.desc",
        }

        if coords:
            params["lat"] = coords[0]
            params["lon"] = coords[1]
            params["range"] = "50mi"

        if date:
            params["datetime_utc.gte"] = f"{date}T00:00:00"

        if query:
            params["q"] = query

        try:
            resp = await fetch_with_retry(
                f"{self.BASE_URL}/events",
                source=self.name,
                params=params,
            )
            data = resp.json()

            events = []
            for ev in data.get("events", []):
                venue = ev.get("venue", {}) or {}
                performers = ev.get("performers", [])

                tags = []
                if ev.get("type"):
                    tags.append(ev["type"])
                for p in performers:
                    if p.get("type"):
                        tags.append(p["type"])
                    for g in p.get("genres", []):
                        if g.get("slug"):
                            tags.append(g["slug"])

                price_str = ""
                stats = ev.get("stats", {})
                low = stats.get("lowest_price")
                high = stats.get("highest_price")
                if low is not None:
                    if low == 0:
                        price_str = "Free"
                    elif high and high != low:
                        price_str = f"${low}-${high}"
                    else:
                        price_str = f"${low}"

                events.append(Event(
                    id=str(ev.get("id", "")),
                    title=ev.get("title", ev.get("short_title", "Untitled")),
                    description=_build_description(ev, performers),
                    source=self.name,
                    url=ev.get("url", ""),
                    venue_name=venue.get("name_v2", venue.get("name", "")),
                    venue_address=venue.get("display_location", venue.get("address", "")),
                    latitude=venue.get("location", {}).get("lat") if isinstance(venue.get("location"), dict) else venue.get("lat"),
                    longitude=venue.get("location", {}).get("lon") if isinstance(venue.get("location"), dict) else venue.get("lon"),
                    start_time=ev.get("datetime_utc", ev.get("datetime_local", "")),
                    end_time="",
                    price=price_str,
                    tags=list(set(tags)),
                    image_url=performers[0].get("image", "") if performers else "",
                    rsvp_count=stats.get("listing_count"),
                ))
            return events

        except Exception as exc:
            log.error("seatgeek.fetch_error", error=str(exc))
            return []


def _build_description(ev: dict, performers: list[dict]) -> str:
    parts = []
    if ev.get("type"):
        parts.append(ev["type"].replace("_", " ").title())
    performer_names = [p.get("name", "") for p in performers[:3] if p.get("name")]
    if performer_names:
        parts.append("ft. " + ", ".join(performer_names))
    venue = ev.get("venue", {}) or {}
    if venue.get("display_location"):
        parts.append(venue["display_location"])
    return " · ".join(parts)
