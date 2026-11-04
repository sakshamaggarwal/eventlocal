"""Integration test — end-to-end demo pipeline without API keys."""
from __future__ import annotations

import asyncio
import pytest

from agents.master_agent import discover_events
from models.user_profile import UserProfile


@pytest.mark.asyncio
async def test_discover_events_demo_mode():
    """Full pipeline works in demo mode (no API keys)."""
    profile = UserProfile(age=28)
    plan = await discover_events(profile=profile, date="2026-11-05", city="bay-area")

    assert plan.events
    assert plan.itinerary_markdown
    assert len(plan.events) > 5
    assert plan.city == "bay-area"


@pytest.mark.asyncio
async def test_discover_events_different_ages():
    """Plan changes meaningfully with different ages."""
    plan_young = await discover_events(
        profile=UserProfile(age=18), date="2026-11-05", city="bay-area"
    )
    plan_old = await discover_events(
        profile=UserProfile(age=55), date="2026-11-05", city="bay-area"
    )

    assert plan_young.events[0].id != plan_old.events[0].id
