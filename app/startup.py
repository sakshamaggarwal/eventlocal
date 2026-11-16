"""
Startup health checks — validates secrets and connectivity on boot.
"""
from __future__ import annotations

import structlog

from app.config import settings
from app import db

log = structlog.get_logger()


async def validate_secrets() -> dict[str, bool]:
    """Check which services have valid configuration."""
    checks: dict[str, bool] = {}

    checks["groq_api_key"] = bool(settings.groq_api_key)
    checks["openrouter_api_key"] = bool(settings.openrouter_api_key)
    checks["any_event_source"] = bool(
        settings.luma_api_key
        or settings.eventbrite_api_key
        or settings.google_places_api_key
        or settings.ticketmaster_api_key
        or settings.yelp_api_key  # deferred — not in active pipeline, but still checked
        or settings.seatgeek_client_id
    )
    checks["supabase"] = bool(settings.supabase_url and settings.supabase_key)

    source_status = {
        "luma": bool(settings.luma_api_key),
        "eventbrite": bool(settings.eventbrite_api_key),
        "google_places": bool(settings.google_places_api_key),
        "ticketmaster": bool(settings.ticketmaster_api_key),
        "yelp": bool(settings.yelp_api_key),  # deferred — client not wired in yet
        "seatgeek": bool(settings.seatgeek_client_id),
    }

    active_sources = [k for k, v in source_status.items() if v]
    log.info(
        "startup.secrets_check",
        groq=checks["groq_api_key"],
        supabase=checks["supabase"],
        active_sources=active_sources,
        source_count=len(active_sources),
    )

    if checks["supabase"]:
        db_health = await db.health_check()
        checks["supabase_connected"] = db_health.get("supabase_connected", False)
        log.info("startup.db_health", **db_health)
    else:
        checks["supabase_connected"] = False

    if not checks["groq_api_key"]:
        if checks["openrouter_api_key"]:
            log.info("startup.openrouter_failover", msg="GROQ_API_KEY not set — OpenRouter will be used as primary")
        else:
            log.warning("startup.no_llm_key", msg="Neither GROQ_API_KEY nor OPENROUTER_API_KEY set — LLM features disabled")

    if not checks["any_event_source"]:
        log.warning("startup.no_event_sources", msg="No event source API keys — only demo mode available")

    return checks
