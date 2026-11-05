"""Tests for triggers/ — definitions, mock backend, integration bridge."""
from __future__ import annotations

import pytest

from triggers.definitions import (
    TRIGGER_DEFINITIONS,
    TriggerDefinition,
    EventTriggerType,
    get_trigger_definition,
    get_triggers_by_type,
)
from triggers.client import (
    TriggerwareIntegration,
    MockTriggerBackend,
    LiveTriggerBackend,
    TriggerDelta,
)


# ---------------------------------------------------------------------------
# Trigger definitions
# ---------------------------------------------------------------------------

class TestTriggerDefinitions:
    def test_all_definitions_present(self):
        expected = {
            "new_bay_area_events",
            "price_drops",
            "trending_events",
            "venue_updates",
            "sold_out_events",
        }
        assert set(TRIGGER_DEFINITIONS.keys()) == expected

    def test_definition_structure(self):
        for name, defn in TRIGGER_DEFINITIONS.items():
            assert isinstance(defn, TriggerDefinition)
            assert defn.name == name
            assert defn.description
            assert defn.sql
            assert defn.schedule
            assert isinstance(defn.trigger_type, EventTriggerType)

    def test_get_trigger_definition(self):
        defn = get_trigger_definition("price_drops")
        assert defn is not None
        assert defn.trigger_type == EventTriggerType.PRICE_DROP

    def test_get_trigger_definition_unknown(self):
        assert get_trigger_definition("nonexistent") is None

    def test_get_triggers_by_type(self):
        new_event_triggers = get_triggers_by_type(EventTriggerType.NEW_EVENTS)
        assert len(new_event_triggers) == 1
        assert new_event_triggers[0].name == "new_bay_area_events"

    def test_trigger_types_complete(self):
        assert len(EventTriggerType) == 5
        assert EventTriggerType.NEW_EVENTS.value == "new_events"
        assert EventTriggerType.SOLD_OUT.value == "sold_out"


# ---------------------------------------------------------------------------
# Mock backend
# ---------------------------------------------------------------------------

class TestMockBackend:
    @pytest.fixture
    def backend(self):
        return MockTriggerBackend()

    @pytest.fixture
    def sample_defn(self):
        return TriggerDefinition(
            name="test_trigger",
            trigger_type=EventTriggerType.NEW_EVENTS,
            description="Test trigger",
            sql="SELECT * FROM events",
            schedule="* * * * *",
        )

    @pytest.mark.asyncio
    async def test_create_trigger(self, backend, sample_defn):
        result = await backend.create_trigger(sample_defn)
        assert result["name"] == "test_trigger"
        assert result["enabled"] is True

    @pytest.mark.asyncio
    async def test_list_triggers(self, backend, sample_defn):
        await backend.create_trigger(sample_defn)
        names = await backend.list_triggers()
        assert "test_trigger" in names

    @pytest.mark.asyncio
    async def test_run_trigger(self, backend, sample_defn):
        await backend.create_trigger(sample_defn)
        delta = await backend.run_trigger("test_trigger")
        assert isinstance(delta, TriggerDelta)
        assert delta.trigger_name == "test_trigger"
        assert delta.added == []
        assert delta.deleted == []

    @pytest.mark.asyncio
    async def test_run_missing_trigger(self, backend):
        with pytest.raises(ValueError, match="not found"):
            await backend.run_trigger("nonexistent")

    @pytest.mark.asyncio
    async def test_inject_delta(self, backend, sample_defn):
        await backend.create_trigger(sample_defn)
        delta = TriggerDelta(
            trigger_name="test_trigger",
            added=[{"id": "e1", "title": "Jazz Night"}],
        )
        await backend.inject_delta("test_trigger", delta)
        polled = await backend.poll("test_trigger")
        assert len(polled) == 1
        assert polled[0].added[0]["title"] == "Jazz Night"

    @pytest.mark.asyncio
    async def test_poll_clears_deltas(self, backend, sample_defn):
        await backend.create_trigger(sample_defn)
        await backend.run_trigger("test_trigger")
        await backend.poll("test_trigger")
        second_poll = await backend.poll("test_trigger")
        assert second_poll == []

    @pytest.mark.asyncio
    async def test_watch_receives_callback(self, backend, sample_defn):
        await backend.create_trigger(sample_defn)
        received = []

        async def on_delta(added, deleted):
            received.append({"added": added, "deleted": deleted})

        await backend.watch("test_trigger", on_delta)
        delta = TriggerDelta(
            trigger_name="test_trigger",
            added=[{"id": "e1"}],
        )
        await backend.inject_delta("test_trigger", delta)
        assert len(received) == 1
        assert received[0]["added"] == [{"id": "e1"}]

    @pytest.mark.asyncio
    async def test_unwatch(self, backend, sample_defn):
        await backend.create_trigger(sample_defn)
        await backend.watch("test_trigger", lambda a, d: None)
        await backend.unwatch("test_trigger")
        assert "test_trigger" not in backend._watchers

    @pytest.mark.asyncio
    async def test_delete_trigger(self, backend, sample_defn):
        await backend.create_trigger(sample_defn)
        await backend.delete_trigger("test_trigger")
        names = await backend.list_triggers()
        assert "test_trigger" not in names

    @pytest.mark.asyncio
    async def test_enable_disable(self, backend, sample_defn):
        await backend.create_trigger(sample_defn)
        await backend.disable_trigger("test_trigger")
        t = await backend.get_trigger("test_trigger")
        assert t["enabled"] is False
        await backend.enable_trigger("test_trigger")
        t = await backend.get_trigger("test_trigger")
        assert t["enabled"] is True

    @pytest.mark.asyncio
    async def test_health(self, backend):
        assert await backend.health() is True


# ---------------------------------------------------------------------------
# TriggerDelta
# ---------------------------------------------------------------------------

class TestTriggerDelta:
    def test_has_changes_empty(self):
        delta = TriggerDelta(trigger_name="t")
        assert delta.has_changes is False

    def test_has_changes_with_added(self):
        delta = TriggerDelta(trigger_name="t", added=[{"id": "1"}])
        assert delta.has_changes is True

    def test_has_changes_with_deleted(self):
        delta = TriggerDelta(trigger_name="t", deleted=[{"id": "1"}])
        assert delta.has_changes is True


# ---------------------------------------------------------------------------
# TriggerwareIntegration
# ---------------------------------------------------------------------------

class TestTriggerwareIntegration:
    @pytest.fixture
    def integration(self):
        return TriggerwareIntegration(backend=MockTriggerBackend())

    @pytest.mark.asyncio
    async def test_is_mock(self, integration):
        assert integration.is_mock is True

    @pytest.mark.asyncio
    async def test_setup_triggers(self, integration):
        created = await integration.setup_triggers()
        assert len(created) == 5
        assert "new_bay_area_events" in created

    @pytest.mark.asyncio
    async def test_setup_custom_definitions(self, integration):
        custom = {
            "custom": TriggerDefinition(
                name="custom",
                trigger_type=EventTriggerType.NEW_EVENTS,
                description="Custom",
                sql="SELECT 1",
                schedule="* * * * *",
            )
        }
        created = await integration.setup_triggers(custom)
        assert created == ["custom"]

    @pytest.mark.asyncio
    async def test_run_trigger(self, integration):
        await integration.setup_triggers()
        delta = await integration.run_trigger("new_bay_area_events")
        assert isinstance(delta, TriggerDelta)

    @pytest.mark.asyncio
    async def test_watch_trigger(self, integration):
        await integration.setup_triggers()
        token = await integration.watch_trigger("price_drops")
        assert token.startswith("mock-resume-")

    @pytest.mark.asyncio
    async def test_watch_all(self, integration):
        await integration.setup_triggers()
        tokens = await integration.watch_all()
        assert len(tokens) == 5

    @pytest.mark.asyncio
    async def test_unwatch_trigger(self, integration):
        await integration.setup_triggers()
        await integration.watch_trigger("price_drops")
        await integration.unwatch_trigger("price_drops")
        assert "price_drops" not in integration._resume_tokens

    @pytest.mark.asyncio
    async def test_poll_trigger(self, integration):
        await integration.setup_triggers()
        await integration.run_trigger("trending_events")
        deltas = await integration.poll_trigger("trending_events")
        assert isinstance(deltas, list)

    @pytest.mark.asyncio
    async def test_status(self, integration):
        await integration.setup_triggers()
        status = await integration.status()
        assert status["mode"] == "mock"
        assert status["triggers_registered"] == 5
        assert "new_bay_area_events" in status["trigger_names"]

    @pytest.mark.asyncio
    async def test_delta_log(self, integration):
        await integration.setup_triggers()
        mock = integration.backend
        delta = TriggerDelta(
            trigger_name="new_bay_area_events",
            added=[{"id": "e1", "title": "Test Event", "source": "luma"}],
            timestamp=1000.0,
        )
        await mock.inject_delta("new_bay_area_events", delta)
        await integration.poll_trigger("new_bay_area_events")
        assert len(integration.delta_log) >= 1

    @pytest.mark.asyncio
    async def test_rows_to_events(self):
        rows = [
            {
                "id": "e1",
                "title": "Jazz Night",
                "source": "luma",
                "venue_name": "The Blue Note",
                "start_time": "2026-11-05T20:00",
                "price": "$25",
                "tags": "jazz, live-music",
            },
            {
                "id": "e2",
                "title": "EDM Rave",
                "tags": ["edm", "rave"],
            },
        ]
        events = TriggerwareIntegration._rows_to_events(rows)
        assert len(events) == 2
        assert events[0].title == "Jazz Night"
        assert "jazz" in events[0].tags
        assert events[1].tags == ["edm", "rave"]

    @pytest.mark.asyncio
    async def test_rows_to_events_bad_row(self):
        rows = [{"weird_field": 42}]
        events = TriggerwareIntegration._rows_to_events(rows)
        assert len(events) == 1
        assert events[0].id == ""

    def test_default_integration_is_mock(self):
        integration = TriggerwareIntegration()
        assert integration.is_mock is True


# ---------------------------------------------------------------------------
# LiveTriggerBackend (construction only, no server)
# ---------------------------------------------------------------------------

class TestLiveTriggerBackend:
    def test_init(self):
        backend = LiveTriggerBackend("localhost:5221")
        assert backend._url == "localhost:5221"
        assert backend._client is None

    def test_init_with_api_key(self):
        backend = LiveTriggerBackend("wss://tw.example.com", api_key="key123")
        assert backend._api_key == "key123"
