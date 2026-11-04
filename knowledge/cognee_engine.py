"""
Cognee integration — the "Event Brain" knowledge graph.

Cognee turns raw event data + venue reviews into a queryable
knowledge graph. This is the core differentiator for the hackathon:
it's a company-brain for a city's event ecosystem.

Key Cognee operations:
- cognee.add()     → ingest data (events, reviews, venue info)
- cognee.cognify() → build knowledge graph relationships
- cognee.search()  → query the graph with natural language
- cognee.memify()  → persist learned patterns across sessions
"""
from __future__ import annotations

import json
import structlog

from models.user_profile import Event

log = structlog.get_logger()

# Cognee may not be installed yet — graceful fallback
try:
    import cognee
    COGNEE_AVAILABLE = True
except ImportError:
    COGNEE_AVAILABLE = False
    log.warning("cognee.not_installed", msg="cognee not installed — running without knowledge graph")


class CogneeEngine:
    """Wrapper around Cognee for the eventlocal knowledge graph."""

    def __init__(self):
        self._initialized = False

    async def _ensure_init(self):
        """Initialize Cognee on first use."""
        if self._initialized or not COGNEE_AVAILABLE:
            return
        try:
            await cognee.prune.prune_system(metadata=True)
            self._initialized = True
            log.info("cognee.initialized")
        except Exception as exc:
            log.error("cognee.init_error", error=str(exc))

    async def ingest_events(self, events: list[Event]) -> None:
        """Feed events into the knowledge graph."""
        if not COGNEE_AVAILABLE or not events:
            return

        await self._ensure_init()

        # Convert events to text documents for Cognee
        docs = []
        for ev in events:
            doc = (
                f"Event: {ev.title}\n"
                f"Source: {ev.source}\n"
                f"Venue: {ev.venue_name} at {ev.venue_address}\n"
                f"Time: {ev.start_time} to {ev.end_time}\n"
                f"Price: {ev.price}\n"
                f"Tags: {', '.join(ev.tags)}\n"
                f"Description: {ev.description[:300]}\n"
            )
            docs.append(doc)

        try:
            # Add all event docs
            text_block = "\n---\n".join(docs)
            await cognee.add(text_block, dataset_name="events")
            log.info("cognee.ingested", count=len(docs))

            # Build the knowledge graph
            await cognee.cognify()
            log.info("cognee.cognified")

        except Exception as exc:
            log.error("cognee.ingest_error", error=str(exc))

    async def ingest_reviews(self, reviews: list[dict], venue_name: str) -> None:
        """Feed venue reviews into the knowledge graph."""
        if not COGNEE_AVAILABLE or not reviews:
            return

        await self._ensure_init()

        docs = []
        for rev in reviews:
            doc = (
                f"Review for {venue_name}:\n"
                f"Rating: {rev.get('rating', 'N/A')}/5\n"
                f"Text: {rev.get('text', '')}\n"
                f"Time: {rev.get('relative_time_description', '')}\n"
            )
            docs.append(doc)

        try:
            text_block = "\n---\n".join(docs)
            await cognee.add(text_block, dataset_name="reviews")
            await cognee.cognify()
            log.info("cognee.reviews_ingested", venue=venue_name, count=len(docs))
        except Exception as exc:
            log.error("cognee.review_ingest_error", error=str(exc))

    async def ingest_training_data(self, text: str, dataset_name: str = "training") -> None:
        """
        Ingest raw training data — e.g. past event-planning chat logs.
        This is the 'secret weapon' for the hackathon: real user experiences
        from months of event planning in Seattle and Bay Area.
        """
        if not COGNEE_AVAILABLE or not text:
            return

        await self._ensure_init()

        try:
            await cognee.add(text, dataset_name=dataset_name)
            await cognee.cognify()
            log.info("cognee.training_ingested", dataset=dataset_name, chars=len(text))
        except Exception as exc:
            log.error("cognee.training_ingest_error", error=str(exc))

    async def search(self, query: str) -> str:
        """Query the knowledge graph and return context as text."""
        if not COGNEE_AVAILABLE:
            return ""

        await self._ensure_init()

        try:
            results = await cognee.search(query)
            log.info("cognee.search", query=query[:80], results=len(results) if results else 0)

            if not results:
                return ""

            # Format results as context text
            context_parts = []
            for r in results:
                if isinstance(r, dict):
                    context_parts.append(json.dumps(r, indent=2))
                else:
                    context_parts.append(str(r))

            return "\n\n".join(context_parts)

        except Exception as exc:
            log.error("cognee.search_error", error=str(exc))
            return ""

    async def remember(self) -> None:
        """Persist learned patterns (memify) for future sessions."""
        if not COGNEE_AVAILABLE:
            return

        try:
            await cognee.memify()
            log.info("cognee.memified")
        except Exception as exc:
            log.error("cognee.memify_error", error=str(exc))
