"""
Yelp Fusion API — venue discovery and reviews for the knowledge graph.
Docs: https://docs.developer.yelp.com/reference/v3_business_search
Free tier: 5000 calls/day.

Yelp does not have a dedicated events endpoint, so this source finds
venues (bars, restaurants, nightlife) and pulls their reviews — feeding
the Cognee knowledge graph with crowd/atmosphere data.
"""
from __future__ import annotations

import structlog
from app.config import settings
from models.user_profile import Event
from sources.base import EventSource
from sources.http_utils import fetch_with_retry

log = structlog.get_logger()

CITY_LOCATIONS = {
    "bay-area": "San Francisco, CA",
    "seattle": "Seattle, WA",
    "los-angeles": "Los Angeles, CA",
    "new-york": "New York, NY",
}


class YelpClient(EventSource):
    name = "yelp"

    BASE_URL = "https://api.yelp.com/v3"

    async def fetch_events(
        self,
        city: str,
        date: str,
        *,
        query: str = "",
        limit: int = 25,
    ) -> list[Event]:
        if not settings.yelp_api_key:
            log.warning("yelp.no_api_key", msg="Skipping Yelp — no API key set")
            return []

        headers = {"Authorization": f"Bearer {settings.yelp_api_key}"}
        location = CITY_LOCATIONS.get(city, city)

        params: dict = {
            "location": location,
            "categories": "nightlife,bars,musicvenues,comedyclubs,danceclubs,cocktailbars",
            "sort_by": "rating",
            "limit": min(limit, 50),
        }
        if query:
            params["term"] = query

        try:
            resp = await fetch_with_retry(
                f"{self.BASE_URL}/businesses/search",
                source=self.name,
                headers=headers,
                params=params,
            )
            data = resp.json()

            events = []
            for biz in data.get("businesses", []):
                coords = biz.get("coordinates", {})
                loc = biz.get("location", {})

                tags = [c.get("alias", "") for c in biz.get("categories", [])]
                if biz.get("price"):
                    tags.append(f"price-{biz['price']}")

                events.append(Event(
                    id=biz.get("id", ""),
                    title=biz.get("name", ""),
                    description=_build_description(biz),
                    source=self.name,
                    url=biz.get("url", ""),
                    venue_name=biz.get("name", ""),
                    venue_address=", ".join(loc.get("display_address", [])),
                    latitude=coords.get("latitude"),
                    longitude=coords.get("longitude"),
                    tags=tags,
                    price=biz.get("price", ""),
                    image_url=biz.get("image_url", ""),
                    rsvp_count=biz.get("review_count"),
                ))
            return events

        except Exception as exc:
            log.error("yelp.fetch_error", error=str(exc))
            return []

    async def fetch_reviews(self, business_id: str) -> list[dict]:
        """Fetch reviews for a Yelp business — these go into Cognee."""
        if not settings.yelp_api_key:
            return []

        headers = {"Authorization": f"Bearer {settings.yelp_api_key}"}
        try:
            resp = await fetch_with_retry(
                f"{self.BASE_URL}/businesses/{business_id}/reviews",
                source=self.name,
                headers=headers,
                params={"limit": 3, "sort_by": "yelp_sort"},
            )
            data = resp.json()

            return [
                {
                    "text": r.get("text", ""),
                    "rating": r.get("rating", 0),
                    "source": "yelp",
                    "relative_time_description": r.get("time_created", ""),
                }
                for r in data.get("reviews", [])
            ]
        except Exception as exc:
            log.error("yelp.reviews_error", business_id=business_id, error=str(exc))
            return []


def _build_description(biz: dict) -> str:
    parts = []
    cats = [c.get("title", "") for c in biz.get("categories", [])]
    if cats:
        parts.append(", ".join(cats))
    if biz.get("rating"):
        parts.append(f"{biz['rating']}/5 ({biz.get('review_count', 0)} reviews)")
    if biz.get("price"):
        parts.append(biz["price"])
    loc = biz.get("location", {})
    if loc.get("display_address"):
        parts.append(", ".join(loc["display_address"]))
    return " · ".join(parts)
