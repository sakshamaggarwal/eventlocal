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
from sources import EventbriteClient, GooglePlacesClient, LumaClient
from sources.sample_data import get_sample_events

log = structlog.get_logger()

_SOURCES = [LumaClient(), EventbriteClient(), GooglePlacesClient()]


def _has_any_api_key() -> bool:
    return bool(
        settings.luma_api_key
        or settings.eventbrite_api_key
        or settings.google_places_api_key
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

    # --- 1. Fetch events (live APIs or sample data fallback) ---
    if _has_any_api_key():
        tasks = [src.fetch_events(city, date) for src in _SOURCES]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_events: list[Event] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                log.error("master.source_error", source=_SOURCES[i].name, error=str(result))
            else:
                all_events.extend(result)
    else:
        log.info("master.demo_mode", msg="No API keys set — using sample event data")
        all_events = get_sample_events(city, date)

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
