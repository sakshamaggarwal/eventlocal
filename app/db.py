"""
Supabase persistence layer — user profiles, saved events, KBs, event cache,
and deduplication.

Gracefully no-ops when SUPABASE_URL is not configured (in-memory fallback).
User-specific operations accept an optional *client* parameter: pass an
authenticated client (from ``app.auth.get_authenticated_client``) so that
row-level security policies are enforced.  When *client* is ``None`` the
shared anon client is used (suitable for unauthenticated reads and for
tables without RLS, like ``event_cache``).
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

async def save_user_kb(user_id: str, kb_data: dict, client=None) -> bool:
    """Upsert a user's knowledge base to Supabase."""
    client = client or _get_client()
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


async def load_user_kb(user_id: str, client=None) -> dict | None:
    """Load a user's knowledge base from Supabase."""
    client = client or _get_client()
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
# User profiles
# ---------------------------------------------------------------------------

async def save_profile(user_id: str, profile: dict, client=None) -> bool:
    """Upsert a user profile to Supabase."""
    client = client or _get_client()
    if not client:
        return False
    try:
        client.table("profiles").upsert({
            "id": user_id,
            "email": profile.get("email", ""),
            "display_name": profile.get("display_name", ""),
            "age": profile.get("age", 28),
            "social_mode": profile.get("social_mode", "solo"),
            "city": profile.get("city", "bay-area"),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }, on_conflict="id").execute()
        log.info("db.profile_saved", user_id=user_id)
        return True
    except Exception as exc:
        log.error("db.profile_save_error", user_id=user_id, error=str(exc))
        return False


async def load_profile(user_id: str, client=None) -> dict | None:
    """Load a user profile from Supabase."""
    client = client or _get_client()
    if not client:
        return None
    try:
        resp = (
            client.table("profiles")
            .select("*")
            .eq("id", user_id)
            .maybe_single()
            .execute()
        )
        return resp.data if resp.data else None
    except Exception as exc:
        log.error("db.profile_load_error", user_id=user_id, error=str(exc))
        return None


# ---------------------------------------------------------------------------
# Saved events (per user)
# ---------------------------------------------------------------------------

async def save_event_for_user(
    user_id: str, event_data: dict, date: str = "", client=None
) -> bool:
    """Bookmark an event for the user."""
    client = client or _get_client()
    if not client:
        return False
    try:
        fp = _event_fingerprint(
            event_data.get("title", ""),
            event_data.get("venue_name", ""),
            date or event_data.get("start_time", "")[:10],
        )
        client.table("saved_events").upsert(
            {
                "user_id": user_id,
                "event_fingerprint": fp,
                "event_data": json.dumps(event_data),
            },
            on_conflict="user_id,event_fingerprint",
        ).execute()
        log.info("db.event_saved", user_id=user_id, fp=fp)
        return True
    except Exception as exc:
        log.error("db.event_save_error", user_id=user_id, error=str(exc))
        return False


async def unsave_event_for_user(
    user_id: str, event_fingerprint: str, client=None
) -> bool:
    """Remove an event from the user's saved list."""
    client = client or _get_client()
    if not client:
        return False
    try:
        client.table("saved_events").delete().eq(
            "user_id", user_id
        ).eq("event_fingerprint", event_fingerprint).execute()
        log.info("db.event_unsaved", user_id=user_id, fp=event_fingerprint)
        return True
    except Exception as exc:
        log.error("db.event_unsave_error", user_id=user_id, error=str(exc))
        return False


async def get_saved_events(user_id: str, client=None) -> list[dict]:
    """Return the user's bookmarked events, newest first."""
    client = client or _get_client()
    if not client:
        return []
    try:
        resp = (
            client.table("saved_events")
            .select("*")
            .eq("user_id", user_id)
            .order("saved_at", desc=True)
            .execute()
        )
        if resp.data:
            results = []
            for row in resp.data:
                ev = json.loads(row["event_data"])
                ev["_saved_at"] = row["saved_at"]
                ev["_fingerprint"] = row["event_fingerprint"]
                results.append(ev)
            return results
        return []
    except Exception as exc:
        log.error("db.saved_events_error", user_id=user_id, error=str(exc))
        return []


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
-- =====================================================================
-- eventlocal Supabase schema  (run once via the Supabase SQL Editor)
-- =====================================================================

-- 1. User profiles (auto-created on sign-up via trigger) ---------------

CREATE TABLE IF NOT EXISTS profiles (
    id          UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email       TEXT,
    display_name TEXT,
    age         INTEGER DEFAULT 28 CHECK (age >= 13 AND age <= 100),
    social_mode TEXT DEFAULT 'solo'
                CHECK (social_mode IN ('solo', 'group', 'date')),
    city        TEXT DEFAULT 'bay-area',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Auto-create a profile row when a new user signs up
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.profiles (id, email, display_name)
    VALUES (
        NEW.id,
        NEW.email,
        COALESCE(NEW.raw_user_meta_data ->> 'full_name',
                 NEW.raw_user_meta_data ->> 'name', '')
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- 2. Saved / bookmarked events (per user) ------------------------------

CREATE TABLE IF NOT EXISTS saved_events (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    event_fingerprint TEXT NOT NULL,
    event_data        JSONB NOT NULL,
    saved_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(user_id, event_fingerprint)
);

CREATE INDEX IF NOT EXISTS idx_saved_events_user
    ON saved_events (user_id);

-- 3. User knowledge bases -----------------------------------------------

CREATE TABLE IF NOT EXISTS user_kbs (
    user_id    TEXT PRIMARY KEY,
    kb_data    JSONB NOT NULL DEFAULT '{}',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 4. Event cache with deduplication -------------------------------------

CREATE TABLE IF NOT EXISTS event_cache (
    fingerprint TEXT PRIMARY KEY,
    source      TEXT NOT NULL,
    source_id   TEXT NOT NULL,
    city        TEXT NOT NULL,
    date        TEXT NOT NULL,
    event_data  JSONB NOT NULL,
    fetched_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_event_cache_city_date
    ON event_cache (city, date);
CREATE INDEX IF NOT EXISTS idx_event_cache_fetched
    ON event_cache (fetched_at);

-- 5. Row-Level Security -------------------------------------------------

-- profiles: users can read/write only their own row
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
CREATE POLICY "profiles_select_own" ON profiles
    FOR SELECT USING (auth.uid() = id);
CREATE POLICY "profiles_insert_own" ON profiles
    FOR INSERT WITH CHECK (auth.uid() = id);
CREATE POLICY "profiles_update_own" ON profiles
    FOR UPDATE USING (auth.uid() = id);

-- saved_events: users manage only their own bookmarks
ALTER TABLE saved_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY "saved_events_all_own" ON saved_events
    FOR ALL USING (auth.uid() = user_id);

-- user_kbs: users access only their own KB
ALTER TABLE user_kbs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "user_kbs_all_own" ON user_kbs
    FOR ALL USING (auth.uid()::text = user_id);

-- event_cache: anyone can read, authenticated users can write
ALTER TABLE event_cache ENABLE ROW LEVEL SECURITY;
CREATE POLICY "event_cache_select_all" ON event_cache
    FOR SELECT USING (true);
CREATE POLICY "event_cache_insert_auth" ON event_cache
    FOR INSERT WITH CHECK (auth.role() = 'authenticated');
CREATE POLICY "event_cache_update_auth" ON event_cache
    FOR UPDATE USING (auth.role() = 'authenticated');
"""
