"""
TriggerWare integration — live event monitoring for the Event Brain.

Provides triggers that watch for new events, price drops, and trending
shifts, then auto-refresh the Cognee knowledge graph so the Event Brain
stays current without manual re-ingestion.

Works in two modes:
  - Live: connects to a TriggerWare server (set TRIGGERWARE_URL)
  - Mock: in-memory trigger simulation for development and demo
"""
from triggers.client import (
    TriggerwareIntegration,
    get_integration,
)
from triggers.definitions import (
    TRIGGER_DEFINITIONS,
    EventTriggerType,
)

__all__ = [
    "TriggerwareIntegration",
    "get_integration",
    "TRIGGER_DEFINITIONS",
    "EventTriggerType",
]
