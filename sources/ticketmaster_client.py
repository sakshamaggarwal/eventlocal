"""
Ticketmaster Discovery API — concerts, sports, theater, arts.
Docs: https://developer.ticketmaster.com/products-and-docs/apis/discovery-api/v2/
Free tier: 5000 calls/day.
"""
from __future__ import annotations

import structlog
from app.config import settings
from models.user_profile import Event
from sources.base import EventSource
from sources.http_utils import fetch_with_retry

log = structlog.get_logger()

CITY_COORDS = {
    "bay-area": ("37.7749", "-122.4194"),
    "seattle": ("47.6062", "-122.3321"),
    "los-angeles": ("34.0522", "-118.2437"),
    "new-york": ("40.7128", "-74.0060"),
}


class TicketmasterClient(EventSource):
    name = "ticketmaster"

    BASE_URL = "https://app.ticketmaster.com/discovery/v2"

    async def fetch_events(
        self,
        city: str,
        date: str,
        *,
        query: str = "",
        limit: int = 25,
    ) -> list[Event]:
        if not settings.ticketmaster_api_key:
            log.warning("ticketmaster.no_api_key", msg="Skipping Ticketmaster — no API key set")
            return []

        coords = CITY_COORDS.get(city)
        params: dict = {
            "apikey": settings.ticketmaster_api_key,
            "size": min(limit, 50),
            "sort": "date,asc",
        }

        if coords:
            params["latlong"] = f"{coords[0]},{coords[1]}"
            params["radius"] = "50"
            params["unit"] = "miles"
        else:
            params["city"] = city

        if date:
            params["startDateTime"] = f"{date}T00:00:00Z"

        if query:
            params["keyword"] = query

        try:
            resp = await fetch_with_retry(
                f"{self.BASE_URL}/events.json",
                source=self.name,
                params=params,
            )
            data = resp.json()

            embedded = data.get("_embedded", {})
            events = []
            for ev in embedded.get("events", []):
                venue = {}
                if ev.get("_embedded", {}).get("venues"):
                    venue = ev["_embedded"]["venues"][0]

                location = venue.get("location", {})
                start = ev.get("dates", {}).get("start", {})

                tags = []
                for clf in ev.get("classifications", []):
                    if clf.get("genre", {}).get("name"):
                        tags.append(clf["genre"]["name"].lower())
                    if clf.get("subGenre", {}).get("name"):
                        tags.append(clf["subGenre"]["name"].lower())
                    if clf.get("segment", {}).get("name"):
                        tags.append(clf["segment"]["name"].lower())

                price_str = ""
                if ev.get("priceRanges"):
                    pr = ev["priceRanges"][0]
                    low = pr.get("min", 0)
                    high = pr.get("max", 0)
                    if low == 0 and high == 0:
                        price_str = "Free"
                    elif low == high:
                        price_str = f"${low:.0f}"
                    else:
                        price_str = f"${low:.0f}-${high:.0f}"

                events.append(Event(
                    id=ev.get("id", ""),
                    title=ev.get("name", "Untitled"),
                    description=ev.get("info", ev.get("pleaseNote", "")),
                    source=self.name,
                    url=ev.get("url", ""),
                    venue_name=venue.get("name", ""),
                    venue_address=_venue_address(venue),
                    latitude=float(location["latitude"]) if location.get("latitude") else None,
                    longitude=float(location["longitude"]) if location.get("longitude") else None,
                    start_time=start.get("dateTime", start.get("localDate", "")),
                    end_time="",
                    price=price_str,
                    tags=tags,
                    image_url=ev["images"][0]["url"] if ev.get("images") else "",
                ))
            return events

        except Exception as exc:
            log.error("ticketmaster.fetch_error", error=str(exc))
            return []


def _venue_address(venue: dict) -> str:
    parts = []
    if venue.get("address", {}).get("line1"):
        parts.append(venue["address"]["line1"])
    if venue.get("city", {}).get("name"):
        parts.append(venue["city"]["name"])
    if venue.get("state", {}).get("stateCode"):
        parts.append(venue["state"]["stateCode"])
    return ", ".join(parts)
