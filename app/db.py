"""
Supabase persistence layer — user KBs, event cache, and deduplication.

Gracefully no-ops when SUPABASE_URL is not configured (in-memory fallback).
Tables are auto-created via the Supabase client on first write.
"""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from typing import Any

import structlog

from app.config import settings

log = structlog.get_logger()

_client = None
_available = False


def _get_client():
    global _client, _available
    if _client is not None:
        return _client
    if not settings.supabase_url or not settings.supabase_key:
        log.info("db.supabase_not_configured")
        _available = False
        return None
    try:
        from supabase import create_client
        _client = create_client(settings.supabase_url, settings.supabase_key)
        _available = True
        log.info("db.supabase_connected", url=settings.supabase_url[:40])
        return _client
    except Exception as exc:
        log.error("db.supabase_connect_error", error=str(exc))
        _available = False
        return None


def is_available() -> bool:
    _get_client()
    return _available


# ---------------------------------------------------------------------------
# User KB persistence
# ---------------------------------------------------------------------------

async def save_user_kb(user_id: str, kb_data: dict) -> bool:
    """Upsert a user's knowledge base to Supabase."""
    client = _get_client()
    if not client:
        return False
    try:
        client.table("user_kbs").upsert({
            "user_id": user_id,
            "kb_data": json.dumps(kb_data),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }, on_conflict="user_id").execute()
        log.info("db.kb_saved", user_id=user_id)
        return True
    except Exception as exc:
        log.error("db.kb_save_error", user_id=user_id, error=str(exc))
        return False


async def load_user_kb(user_id: str) -> dict | None:
    """Load a user's knowledge base from Supabase."""
    client = _get_client()
    if not client:
        return None
    try:
        resp = client.table("user_kbs").select("kb_data").eq("user_id", user_id).maybe_single().execute()
        if resp.data:
            return json.loads(resp.data["kb_data"])
        return None
    except Exception as exc:
        log.error("db.kb_load_error", user_id=user_id, error=str(exc))
        return None


# ---------------------------------------------------------------------------
# Event cache & deduplication
# ---------------------------------------------------------------------------

def _event_fingerprint(title: str, venue: str, date: str) -> str:
    """Stable hash for dedup: normalized title + venue + date."""
    norm = f"{title.lower().strip()}|{venue.lower().strip()}|{date.strip()}"
    return hashlib.sha256(norm.encode()).hexdigest()[:16]


async def cache_events(events: list[dict], city: str, date: str) -> int:
    """Cache fetched events to Supabase. Returns count of new events inserted."""
    client = _get_client()
    if not client or not events:
        return 0
    inserted = 0
    now = datetime.now(timezone.utc).isoformat()
    try:
        rows = []
        for ev in events:
            fp = _event_fingerprint(
                ev.get("title", ""),
                ev.get("venue_name", ""),
                date,
            )
            rows.append({
                "fingerprint": fp,
                "source": ev.get("source", ""),
                "source_id": ev.get("id", ""),
                "city": city,
                "date": date,
                "event_data": json.dumps(ev),
                "fetched_at": now,
            })
        resp = client.table("event_cache").upsert(
            rows, on_conflict="fingerprint"
        ).execute()
        inserted = len(resp.data) if resp.data else 0
        log.info("db.events_cached", city=city, date=date, count=inserted)
    except Exception as exc:
        log.error("db.event_cache_error", error=str(exc))
    return inserted


async def get_cached_events(city: str, date: str, max_age_seconds: int = 3600) -> list[dict] | None:
    """Load cached events if fresh enough. Returns None if cache miss or stale."""
    client = _get_client()
    if not client:
        return None
    try:
        cutoff = datetime.fromtimestamp(
            time.time() - max_age_seconds, tz=timezone.utc
        ).isoformat()
        resp = (
            client.table("event_cache")
            .select("event_data")
            .eq("city", city)
            .eq("date", date)
            .gte("fetched_at", cutoff)
            .execute()
        )
        if resp.data:
            events = [json.loads(row["event_data"]) for row in resp.data]
            log.info("db.cache_hit", city=city, date=date, count=len(events))
            return events
        return None
    except Exception as exc:
        log.error("db.cache_load_error", error=str(exc))
        return None


def deduplicate_events(events: list[Any], date: str) -> list[Any]:
    """Remove duplicate events by fingerprint. Works on Event model objects."""
    seen: set[str] = set()
    unique = []
    for ev in events:
        title = getattr(ev, "title", "") or ""
        venue = getattr(ev, "venue_name", "") or ""
        fp = _event_fingerprint(title, venue, date)
        if fp not in seen:
            seen.add(fp)
            unique.append(ev)
    removed = len(events) - len(unique)
    if removed:
        log.info("db.dedup", removed=removed, kept=len(unique))
    return unique


# ---------------------------------------------------------------------------
# Startup health check
# ---------------------------------------------------------------------------

async def health_check() -> dict[str, Any]:
    """Verify Supabase connectivity and table access."""
    result: dict[str, Any] = {"supabase_configured": bool(settings.supabase_url)}
    client = _get_client()
    if not client:
        result["supabase_connected"] = False
        return result
    try:
        resp = client.table("user_kbs").select("user_id").limit(1).execute()
        result["supabase_connected"] = True
        result["user_kbs_table"] = True
    except Exception as exc:
        result["supabase_connected"] = True
        result["user_kbs_table"] = False
        result["error"] = str(exc)
    return result


# ---------------------------------------------------------------------------
# SQL schema for Supabase (run once via Supabase SQL editor)
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
-- User knowledge bases
CREATE TABLE IF NOT EXISTS user_kbs (
    user_id TEXT PRIMARY KEY,
    kb_data JSONB NOT NULL DEFAULT '{}',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Event cache with deduplication
CREATE TABLE IF NOT EXISTS event_cache (
    fingerprint TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    source_id TEXT NOT NULL,
    city TEXT NOT NULL,
    date TEXT NOT NULL,
    event_data JSONB NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_event_cache_city_date ON event_cache (city, date);
CREATE INDEX IF NOT EXISTS idx_event_cache_fetched ON event_cache (fetched_at);

-- Row-level security (enable after setting up auth)
-- ALTER TABLE user_kbs ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "users_own_kb" ON user_kbs
--   USING (auth.uid()::text = user_id);
"""
