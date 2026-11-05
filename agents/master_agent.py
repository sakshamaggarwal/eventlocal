"""
Master Agent — orchestrates event fetching, scoring, and plan generation.

Hackathon MVP flow:
1. Fetch events from all configured sources (or sample data in demo mode)
2. Feed events + reviews into Cognee two-tier knowledge graph
3. Apply age personalization layer
4. Search Cognee for context-enriched, user-personalized results
5. Pass ranked events to Planner Agent for itinerary
"""
from __future__ import annotations

import asyncio
import structlog

from agents.layers.age_layer import apply_age_scores
from agents.planner_agent import generate_plan
from app.config import settings
from knowledge.cognee_engine import TwoTierCogneeEngine
from models.user_profile import Event, EveningPlan, UserProfile
from sources import (
    EventbriteClient,
    GooglePlacesClient,
    LumaClient,
    SeatGeekClient,
    TicketmasterClient,
    YelpClient,
)
from sources.sample_data import get_sample_events

log = structlog.get_logger()

_SOURCES = [
    LumaClient(),
    EventbriteClient(),
    GooglePlacesClient(),
    TicketmasterClient(),
    YelpClient(),
    SeatGeekClient(),
]


def _has_any_api_key() -> bool:
    return bool(
        settings.luma_api_key
        or settings.eventbrite_api_key
        or settings.google_places_api_key
        or settings.ticketmaster_api_key
        or settings.yelp_api_key
        or settings.seatgeek_client_id
    )


async def discover_events(
    profile: UserProfile,
    date: str,
    city: str | None = None,
    user_id: str | None = None,
) -> EveningPlan:
    """Full pipeline: fetch -> cognify -> score -> plan."""
    city = city or settings.city
    log.info("master.start", city=city, date=date, age=profile.age, user_id=user_id)

    # --- 1. Fetch events from all configured sources ---
    demo_mode = settings.app_env == "demo" and not _has_any_api_key()
    if demo_mode:
        log.info("master.demo_mode", msg="Demo mode — using sample event data")
        all_events: list[Event] = get_sample_events(city, date)
    else:
        if not _has_any_api_key():
            log.warning("master.no_api_keys", msg="No event-source API keys configured")
        tasks = [src.fetch_events(city, date) for src in _SOURCES]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_events = []
        source_hits: dict[str, int] = {}
        for i, result in enumerate(results):
            src_name = _SOURCES[i].name
            if isinstance(result, Exception):
                log.error("master.source_error", source=src_name, error=str(result))
            else:
                source_hits[src_name] = len(result)
                all_events.extend(result)
        log.info("master.sources", hits=source_hits)

    log.info("master.fetched", total=len(all_events))

    if not all_events:
        return EveningPlan(
            city=city,
            date=date,
            user_profile=profile,
            events=[],
            itinerary_markdown="No events found for this date and location. Try a different date or check that your API keys are configured.",
            explanation="No events available",
        )

    # --- 2. Feed into Cognee two-tier knowledge graph ---
    engine = TwoTierCogneeEngine()
    await engine.ingest_events(all_events)

    # --- 3. Apply age personalization ---
    scored = apply_age_scores(all_events, profile)

    # --- 4. Search two-tier KB for enriched, personalized context ---
    query = _build_cognee_query(profile, city, date)
    cognee_insights = await engine.search(query, user_id=user_id)

    # --- 5. Generate evening plan ---
    plan = await generate_plan(
        events=scored[:15],
        profile=profile,
        city=city,
        date=date,
        cognee_context=cognee_insights,
    )

    return plan


def _build_cognee_query(profile: UserProfile, city: str, date: str) -> str:
    bracket_desc = {
        "under_21": "under 21, looking for all-ages fun",
        "21_29": "in their twenties, looking for nightlife and social events",
        "30_39": "in their thirties, looking for quality experiences",
        "40_49": "in their forties, looking for refined entertainment",
        "50_plus": "over 50, looking for cultural and relaxed outings",
    }
    age_desc = bracket_desc.get(profile.age_bracket.value, "")

    return (
        f"Best events and venues in {city} on {date} for someone {age_desc}. "
        f"Include venue reviews, crowd demographics, and atmosphere details."
    )
