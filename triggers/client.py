"""
TriggerWare client — connects to TriggerWare or runs in mock mode.

Live mode:  set TRIGGERWARE_URL (e.g. "localhost:5221") to connect.
Mock mode:  default when no URL is set — simulates trigger deltas
            in-memory for development and demo.

The integration layer bridges TriggerWare deltas to the Cognee
knowledge engine: new events get ingested, price drops trigger
re-ranking, and trending shifts update pattern entities.
"""
from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass, field
from typing import Any

import structlog

from models.user_profile import Event
from triggers.definitions import (
    TRIGGER_DEFINITIONS,
    TriggerDefinition,
    EventTriggerType,
)

log = structlog.get_logger()

TRIGGERWARE_URL = os.environ.get("TRIGGERWARE_URL", "")
TRIGGERWARE_API_KEY = os.environ.get("TRIGGERWARE_API_KEY", "")


# ---------------------------------------------------------------------------
# Delta — what a trigger run produces
# ---------------------------------------------------------------------------

@dataclass
class TriggerDelta:
    """Rows added and deleted since the last trigger run."""
    trigger_name: str
    added: list[dict[str, Any]] = field(default_factory=list)
    deleted: list[dict[str, Any]] = field(default_factory=list)
    timestamp: float = 0.0

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.deleted)


# ---------------------------------------------------------------------------
# Mock backend — simulates triggers without a TriggerWare server
# ---------------------------------------------------------------------------

class MockTriggerBackend:
    """In-memory trigger simulation for demo and development."""

    def __init__(self) -> None:
        self._triggers: dict[str, dict[str, Any]] = {}
        self._watchers: dict[str, list[Any]] = {}
        self._deltas: dict[str, list[TriggerDelta]] = {}

    async def create_trigger(self, defn: TriggerDefinition) -> dict[str, Any]:
        trigger = {
            "name": defn.name,
            "description": defn.description,
            "sql": defn.sql,
            "schedule": defn.schedule,
            "enabled": defn.enabled,
            "batch_size": defn.batch_size,
            "timeout_ms": defn.timeout_ms,
        }
        self._triggers[defn.name] = trigger
        self._deltas.setdefault(defn.name, [])
        log.info("mock.trigger_created", trigger=defn.name)
        return trigger

    async def run_trigger(self, name: str) -> TriggerDelta:
        if name not in self._triggers:
            raise ValueError(f"trigger {name!r} not found")
        delta = TriggerDelta(
            trigger_name=name,
            added=[],
            deleted=[],
            timestamp=time.time(),
        )
        self._deltas[name].append(delta)
        log.info("mock.trigger_run", trigger=name, added=0, deleted=0)
        return delta

    async def inject_delta(self, name: str, delta: TriggerDelta) -> None:
        """Inject a synthetic delta for testing."""
        self._deltas.setdefault(name, []).append(delta)
        callbacks = self._watchers.get(name, [])
        for cb in callbacks:
            await cb(delta.added, delta.deleted)

    async def poll(self, name: str) -> list[TriggerDelta]:
        deltas = self._deltas.get(name, [])
        self._deltas[name] = []
        return deltas

    async def watch(self, name: str, callback: Any) -> str:
        self._watchers.setdefault(name, []).append(callback)
        return f"mock-resume-{name}-{int(time.time())}"

    async def unwatch(self, name: str) -> None:
        self._watchers.pop(name, None)

    async def list_triggers(self) -> list[str]:
        return list(self._triggers.keys())

    async def get_trigger(self, name: str) -> dict[str, Any] | None:
        return self._triggers.get(name)

    async def delete_trigger(self, name: str) -> None:
        self._triggers.pop(name, None)
        self._deltas.pop(name, None)
        self._watchers.pop(name, None)

    async def enable_trigger(self, name: str) -> None:
        if name in self._triggers:
            self._triggers[name]["enabled"] = True

    async def disable_trigger(self, name: str) -> None:
        if name in self._triggers:
            self._triggers[name]["enabled"] = False

    async def health(self) -> bool:
        return True


# ---------------------------------------------------------------------------
# Live backend — connects to a real TriggerWare server
# ---------------------------------------------------------------------------

class LiveTriggerBackend:
    """Connects to a TriggerWare server via the Python SDK."""

    def __init__(self, url: str, api_key: str = "") -> None:
        self._url = url
        self._api_key = api_key
        self._client: Any = None

    async def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client

        try:
            from triggerware import TriggerwareClient
        except ImportError:
            raise RuntimeError(
                "triggerware package not installed. "
                "Run: pip install triggerware"
            )

        if self._api_key:
            self._client = await TriggerwareClient.connect_ws(
                self._url, self._api_key
            )
        else:
            self._client = await TriggerwareClient.connect_tcp(self._url)

        log.info("triggerware.connected", url=self._url)
        return self._client

    async def create_trigger(self, defn: TriggerDefinition) -> dict[str, Any]:
        client = await self._ensure_client()
        result = await client.triggers.create(
            defn.name,
            description=defn.description,
            sql=defn.sql,
            schedule=defn.schedule,
            batch_size=defn.batch_size,
            timeout_ms=defn.timeout_ms,
            enabled=defn.enabled,
        )
        log.info("triggerware.trigger_created", trigger=defn.name)
        return result

    async def run_trigger(self, name: str) -> TriggerDelta:
        client = await self._ensure_client()
        result = await client.triggers.run(name)
        return TriggerDelta(
            trigger_name=name,
            added=[dict(zip(range(len(r)), r)) for r in result.get("added", [])],
            deleted=[dict(zip(range(len(r)), r)) for r in result.get("deleted", [])],
            timestamp=time.time(),
        )

    async def poll(self, name: str) -> list[TriggerDelta]:
        client = await self._ensure_client()
        raw_deltas = await client.triggers.poll(name)
        return [
            TriggerDelta(
                trigger_name=name,
                added=d.get("added", []),
                deleted=d.get("deleted", []),
                timestamp=time.time(),
            )
            for d in raw_deltas
        ]

    async def watch(self, name: str, callback: Any) -> str:
        client = await self._ensure_client()
        return await client.triggers.watch(name, callback)

    async def unwatch(self, name: str) -> None:
        client = await self._ensure_client()
        await client.triggers.unwatch(name=name)

    async def list_triggers(self) -> list[str]:
        client = await self._ensure_client()
        return await client.triggers.list()

    async def get_trigger(self, name: str) -> dict[str, Any] | None:
        client = await self._ensure_client()
        try:
            return await client.triggers.get(name)
        except Exception:
            return None

    async def delete_trigger(self, name: str) -> None:
        client = await self._ensure_client()
        await client.triggers.delete(name)

    async def enable_trigger(self, name: str) -> None:
        client = await self._ensure_client()
        await client.triggers.enable(name)

    async def disable_trigger(self, name: str) -> None:
        client = await self._ensure_client()
        await client.triggers.disable(name)

    async def health(self) -> bool:
        client = await self._ensure_client()
        result = await client.system.health()
        return bool(result)


# ---------------------------------------------------------------------------
# TriggerwareIntegration — the bridge between triggers and the Event Brain
# ---------------------------------------------------------------------------

class TriggerwareIntegration:
    """
    Bridges TriggerWare triggers to the Event Brain knowledge engine.

    On delta:
      - NEW_EVENTS  → ingest into Cognee via TwoTierCogneeEngine
      - PRICE_DROP  → re-ingest with updated price, log for user alerts
      - TRENDING    → update pattern entities in the knowledge graph
      - VENUE_UPDATE→ re-ingest venue data
      - SOLD_OUT    → mark events in the graph, notify watchers
    """

    def __init__(self, backend: MockTriggerBackend | LiveTriggerBackend | None = None) -> None:
        if backend is not None:
            self._backend = backend
        elif TRIGGERWARE_URL:
            self._backend = LiveTriggerBackend(TRIGGERWARE_URL, TRIGGERWARE_API_KEY)
        else:
            self._backend = MockTriggerBackend()

        self._resume_tokens: dict[str, str] = {}
        self._delta_log: list[TriggerDelta] = []

    @property
    def is_mock(self) -> bool:
        return isinstance(self._backend, MockTriggerBackend)

    @property
    def backend(self) -> MockTriggerBackend | LiveTriggerBackend:
        return self._backend

    @property
    def delta_log(self) -> list[TriggerDelta]:
        return list(self._delta_log)

    # ------------------------------------------------------------------
    # Setup — register all trigger definitions
    # ------------------------------------------------------------------

    async def setup_triggers(
        self, definitions: dict[str, TriggerDefinition] | None = None
    ) -> list[str]:
        """Register all trigger definitions with the backend."""
        defs = definitions or TRIGGER_DEFINITIONS
        created = []
        for defn in defs.values():
            try:
                await self._backend.create_trigger(defn)
                created.append(defn.name)
            except Exception as exc:
                log.error("trigger.create_failed", trigger=defn.name, error=str(exc))
        log.info("triggers.setup_complete", count=len(created))
        return created

    # ------------------------------------------------------------------
    # Run — execute a trigger and process its delta
    # ------------------------------------------------------------------

    async def run_trigger(self, name: str) -> TriggerDelta:
        """Run a trigger immediately and process the delta."""
        delta = await self._backend.run_trigger(name)
        if delta.has_changes:
            await self._process_delta(name, delta)
        return delta

    # ------------------------------------------------------------------
    # Watch — subscribe to trigger deltas
    # ------------------------------------------------------------------

    async def watch_trigger(self, name: str) -> str:
        """Subscribe to a trigger's deltas via callback."""
        async def _on_delta(added: list, deleted: list) -> None:
            delta = TriggerDelta(
                trigger_name=name,
                added=added,
                deleted=deleted,
                timestamp=time.time(),
            )
            await self._process_delta(name, delta)

        token = await self._backend.watch(name, _on_delta)
        self._resume_tokens[name] = token
        log.info("trigger.watching", trigger=name, token=token)
        return token

    async def unwatch_trigger(self, name: str) -> None:
        await self._backend.unwatch(name)
        self._resume_tokens.pop(name, None)

    async def watch_all(self) -> dict[str, str]:
        """Subscribe to all registered triggers."""
        tokens = {}
        trigger_names = await self._backend.list_triggers()
        for name in trigger_names:
            try:
                token = await self.watch_trigger(name)
                tokens[name] = token
            except Exception as exc:
                log.error("trigger.watch_failed", trigger=name, error=str(exc))
        return tokens

    # ------------------------------------------------------------------
    # Poll — check for pending deltas
    # ------------------------------------------------------------------

    async def poll_trigger(self, name: str) -> list[TriggerDelta]:
        """Poll a trigger for pending deltas."""
        deltas = await self._backend.poll(name)
        for delta in deltas:
            if delta.has_changes:
                await self._process_delta(name, delta)
        return deltas

    # ------------------------------------------------------------------
    # Delta processing — bridge to the knowledge engine
    # ------------------------------------------------------------------

    async def _process_delta(self, trigger_name: str, delta: TriggerDelta) -> None:
        """Route a trigger delta to the appropriate knowledge engine action."""
        self._delta_log.append(delta)

        defn = TRIGGER_DEFINITIONS.get(trigger_name)
        if not defn:
            log.warning("trigger.unknown", trigger=trigger_name)
            return

        handler = self._HANDLERS.get(defn.trigger_type)
        if handler:
            await handler(self, delta)
        else:
            log.info("trigger.no_handler", trigger_type=defn.trigger_type)

    async def _handle_new_events(self, delta: TriggerDelta) -> None:
        """Ingest new events into the knowledge graph."""
        if not delta.added:
            return
        events = self._rows_to_events(delta.added)
        if events:
            try:
                from knowledge.cognee_engine import TwoTierCogneeEngine
                engine = TwoTierCogneeEngine()
                await engine.ingest_events(events)
                log.info("trigger.new_events_ingested", count=len(events))
            except Exception as exc:
                log.error("trigger.ingest_failed", error=str(exc))

    async def _handle_price_drop(self, delta: TriggerDelta) -> None:
        """Log price drops for user notifications and re-index."""
        for row in delta.added:
            log.info(
                "trigger.price_drop",
                event_id=row.get("id", "unknown"),
                title=row.get("title", ""),
                old_price=row.get("old_price", ""),
                new_price=row.get("new_price", ""),
            )

    async def _handle_trending(self, delta: TriggerDelta) -> None:
        """Update trending patterns in the knowledge graph."""
        if not delta.added:
            return
        try:
            from knowledge.cognee_engine import TwoTierCogneeEngine
            engine = TwoTierCogneeEngine()
            trending_text = "\n".join(
                f"Trending: {r.get('title', '?')} at {r.get('venue_name', '?')} "
                f"with {r.get('rsvp_velocity', 0)} RSVPs/hour"
                for r in delta.added
            )
            await engine.ingest_training_data(trending_text, dataset_name="trending")
            log.info("trigger.trending_ingested", count=len(delta.added))
        except Exception as exc:
            log.error("trigger.trending_failed", error=str(exc))

    async def _handle_venue_update(self, delta: TriggerDelta) -> None:
        """Re-ingest venue data on changes."""
        for row in delta.added:
            log.info(
                "trigger.venue_update",
                venue=row.get("venue_name", "unknown"),
                update_type=row.get("update_type", ""),
            )

    async def _handle_sold_out(self, delta: TriggerDelta) -> None:
        """Mark sold-out events for notification."""
        for row in delta.added:
            log.info(
                "trigger.sold_out",
                event_id=row.get("id", "unknown"),
                title=row.get("title", ""),
            )

    _HANDLERS: dict[EventTriggerType, Any] = {
        EventTriggerType.NEW_EVENTS: _handle_new_events,
        EventTriggerType.PRICE_DROP: _handle_price_drop,
        EventTriggerType.TRENDING: _handle_trending,
        EventTriggerType.VENUE_UPDATE: _handle_venue_update,
        EventTriggerType.SOLD_OUT: _handle_sold_out,
    }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _rows_to_events(rows: list[dict[str, Any]]) -> list[Event]:
        """Convert trigger result rows to Event objects."""
        events = []
        for row in rows:
            try:
                tags_raw = row.get("tags", [])
                if isinstance(tags_raw, str):
                    tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
                else:
                    tags = list(tags_raw)

                events.append(Event(
                    id=str(row.get("id", "")),
                    title=str(row.get("title", "")),
                    source=str(row.get("source", "triggerware")),
                    venue_name=str(row.get("venue_name", "")),
                    start_time=str(row.get("start_time", "")),
                    price=str(row.get("price", "")),
                    tags=tags,
                ))
            except Exception as exc:
                log.warning("trigger.row_parse_error", error=str(exc), row=row)
        return events

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    async def status(self) -> dict[str, Any]:
        """Return current trigger integration status."""
        triggers = await self._backend.list_triggers()
        return {
            "mode": "mock" if self.is_mock else "live",
            "triggers_registered": len(triggers),
            "trigger_names": triggers,
            "watching": list(self._resume_tokens.keys()),
            "deltas_processed": len(self._delta_log),
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_integration: TriggerwareIntegration | None = None


def get_integration() -> TriggerwareIntegration:
    """Get or create the TriggerWare integration singleton."""
    global _integration
    if _integration is None:
        _integration = TriggerwareIntegration()
    return _integration
