"""
Trigger definitions — what to watch for in the event ecosystem.

Each definition maps to a TriggerWare trigger: a SQL query that runs
on a schedule and reports rows added or deleted since the last run.
"""
from __future__ import annotations

from enum import Enum
from dataclasses import dataclass, field


class EventTriggerType(str, Enum):
    NEW_EVENTS = "new_events"
    PRICE_DROP = "price_drop"
    TRENDING = "trending"
    VENUE_UPDATE = "venue_update"
    SOLD_OUT = "sold_out"


@dataclass
class TriggerDefinition:
    """A trigger that TriggerWare will execute on schedule."""
    name: str
    trigger_type: EventTriggerType
    description: str
    sql: str
    schedule: str  # cron expression
    enabled: bool = True
    batch_size: int = 50
    timeout_ms: int = 30_000
    tags: list[str] = field(default_factory=list)


TRIGGER_DEFINITIONS: dict[str, TriggerDefinition] = {
    "new_bay_area_events": TriggerDefinition(
        name="new_bay_area_events",
        trigger_type=EventTriggerType.NEW_EVENTS,
        description="Watch for new events in the Bay Area from all sources",
        sql=(
            "SELECT id, title, source, venue_name, start_time, price, tags "
            "FROM events "
            "WHERE region = 'bay-area' "
            "AND created_at > :last_run"
        ),
        schedule="*/15 * * * *",  # every 15 minutes
        tags=["bay-area", "new-events"],
    ),
    "price_drops": TriggerDefinition(
        name="price_drops",
        trigger_type=EventTriggerType.PRICE_DROP,
        description="Detect price reductions on tracked events",
        sql=(
            "SELECT id, title, old_price, new_price, venue_name, start_time "
            "FROM event_price_changes "
            "WHERE new_price < old_price "
            "AND changed_at > :last_run"
        ),
        schedule="*/30 * * * *",  # every 30 minutes
        tags=["price-drop", "deals"],
    ),
    "trending_events": TriggerDefinition(
        name="trending_events",
        trigger_type=EventTriggerType.TRENDING,
        description="Detect events gaining rapid RSVP momentum",
        sql=(
            "SELECT id, title, rsvp_count, rsvp_velocity, venue_name "
            "FROM events "
            "WHERE rsvp_velocity > 10 "
            "AND start_time > NOW() "
            "ORDER BY rsvp_velocity DESC "
            "LIMIT 20"
        ),
        schedule="0 * * * *",  # every hour
        tags=["trending", "popular"],
    ),
    "venue_updates": TriggerDefinition(
        name="venue_updates",
        trigger_type=EventTriggerType.VENUE_UPDATE,
        description="Watch for venue info changes (new reviews, closures)",
        sql=(
            "SELECT venue_id, venue_name, update_type, details "
            "FROM venue_changes "
            "WHERE changed_at > :last_run"
        ),
        schedule="0 */6 * * *",  # every 6 hours
        tags=["venues", "updates"],
    ),
    "sold_out_events": TriggerDefinition(
        name="sold_out_events",
        trigger_type=EventTriggerType.SOLD_OUT,
        description="Detect events that just sold out",
        sql=(
            "SELECT id, title, venue_name, start_time, final_rsvp_count "
            "FROM events "
            "WHERE status = 'sold_out' "
            "AND status_changed_at > :last_run"
        ),
        schedule="*/10 * * * *",  # every 10 minutes
        tags=["sold-out", "capacity"],
    ),
}


def get_trigger_definition(name: str) -> TriggerDefinition | None:
    return TRIGGER_DEFINITIONS.get(name)


def get_triggers_by_type(trigger_type: EventTriggerType) -> list[TriggerDefinition]:
    return [t for t in TRIGGER_DEFINITIONS.values() if t.trigger_type == trigger_type]
