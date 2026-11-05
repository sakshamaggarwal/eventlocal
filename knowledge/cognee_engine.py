"""
Two-Tier Knowledge Base — the core of the Event Brain.

┌─────────────────────────────────────┐
│       GLOBAL KNOWLEDGE BASE         │
│  Events + Venues + Reviews + Patterns│
│  Shared · Gets smarter with every   │
│  query from ANY user                │
├─────────────────────────────────────┤
│       USER LOCAL KB (per user)      │
│  Query history · Event choices      │
│  Ratings · Explicit preferences     │
│  Learns YOUR taste specifically     │
└─────────────────────────────────────┘

Search merges both tiers — user context is weighted higher so a jazz
lover gets jazz first, even before global trending events.

Feedback loop: every query, every event chosen/skipped, every rating
feeds back into the user KB.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

import structlog

from knowledge.ontology import (
    ONTOLOGY_PROMPT,
    MULTI_HOP_TEMPLATES,
    Relationship,
    get_query_template,
)
from models.user_profile import Event, UserProfile

log = structlog.get_logger()

try:
    import cognee
    COGNEE_AVAILABLE = True
except ImportError:
    COGNEE_AVAILABLE = False
    log.warning("cognee.not_installed", msg="cognee not installed — running without knowledge graph")


# ---------------------------------------------------------------------------
# User-local knowledge store (in-memory for hackathon MVP)
# ---------------------------------------------------------------------------

@dataclass
class UserFeedback:
    """A single feedback signal from a user interaction."""
    event_id: str
    action: str              # "chosen", "skipped", "rated"
    value: float = 0.0       # rating value (1-5) or 1.0/0.0 for chosen/skipped
    timestamp: float = 0.0
    tags: list[str] = field(default_factory=list)


@dataclass
class UserKnowledgeBase:
    """Per-user knowledge: preferences learned from interactions."""
    user_id: str
    query_history: list[str] = field(default_factory=list)
    feedback: list[UserFeedback] = field(default_factory=list)
    preferred_vibes: dict[str, float] = field(default_factory=dict)   # vibe → affinity score
    preferred_venues: dict[str, float] = field(default_factory=dict)  # venue → affinity
    preferred_tags: dict[str, float] = field(default_factory=dict)    # tag → affinity
    avoided_tags: dict[str, float] = field(default_factory=dict)      # tag → penalty

    def record_query(self, query: str) -> None:
        self.query_history.append(query)

    def record_feedback(self, event: Event, action: str, value: float = 0.0) -> None:
        fb = UserFeedback(
            event_id=event.id,
            action=action,
            value=value,
            timestamp=time.time(),
            tags=list(event.tags),
        )
        self.feedback.append(fb)
        self._update_preferences(event, action, value)

    def _update_preferences(self, event: Event, action: str, value: float) -> None:
        """Update preference scores based on feedback."""
        if action == "chosen":
            weight = 0.1
        elif action == "rated":
            weight = (value - 3.0) * 0.05  # positive for 4-5, negative for 1-2
        elif action == "skipped":
            weight = -0.05
        else:
            return

        for tag in event.tags:
            tag_lower = tag.lower()
            if weight > 0:
                self.preferred_tags[tag_lower] = self.preferred_tags.get(tag_lower, 0.0) + weight
            else:
                self.avoided_tags[tag_lower] = self.avoided_tags.get(tag_lower, 0.0) + abs(weight)

        if event.venue_name:
            self.preferred_venues[event.venue_name] = (
                self.preferred_venues.get(event.venue_name, 0.0) + weight
            )

    def get_preference_context(self) -> str:
        """Return a text summary of user preferences for search augmentation."""
        parts = []

        top_tags = sorted(self.preferred_tags.items(), key=lambda x: x[1], reverse=True)[:10]
        if top_tags:
            parts.append("Preferred tags: " + ", ".join(f"{t} ({s:.1f})" for t, s in top_tags))

        avoided = sorted(self.avoided_tags.items(), key=lambda x: x[1], reverse=True)[:5]
        if avoided:
            parts.append("Avoided tags: " + ", ".join(f"{t} ({s:.1f})" for t, s in avoided))

        top_venues = sorted(self.preferred_venues.items(), key=lambda x: x[1], reverse=True)[:5]
        if top_venues:
            parts.append("Preferred venues: " + ", ".join(f"{v} ({s:.1f})" for v, s in top_venues))

        recent_queries = self.query_history[-5:]
        if recent_queries:
            parts.append("Recent searches: " + "; ".join(recent_queries))

        return "\n".join(parts) if parts else ""


# ---------------------------------------------------------------------------
# Two-Tier Cognee Engine
# ---------------------------------------------------------------------------

# In-memory user KB store (keyed by user_id)
_user_kbs: dict[str, UserKnowledgeBase] = {}


def get_user_kb(user_id: str) -> UserKnowledgeBase:
    """Get or create a user's local knowledge base."""
    if user_id not in _user_kbs:
        _user_kbs[user_id] = UserKnowledgeBase(user_id=user_id)
    return _user_kbs[user_id]


class TwoTierCogneeEngine:
    """
    Two-tier knowledge engine: global KB (Cognee) + per-user local KB.

    The global tier holds events, venues, reviews, and patterns shared
    across all users. The local tier stores each user's query history,
    chosen/skipped events, ratings, and derived preferences.

    Search merges both: user preferences are weighted 1.5x higher than
    global relevance so that personalization wins ties.
    """

    USER_WEIGHT = 1.5
    GLOBAL_WEIGHT = 1.0

    def __init__(self) -> None:
        self._initialized = False

    async def _ensure_init(self) -> None:
        if self._initialized or not COGNEE_AVAILABLE:
            return
        try:
            await cognee.prune.prune_system(metadata=True)
            self._initialized = True
            log.info("cognee.initialized")
        except Exception as exc:
            log.error("cognee.init_error", error=str(exc))

    # ------------------------------------------------------------------
    # Global KB — ingest
    # ------------------------------------------------------------------

    async def ingest_events(self, events: list[Event]) -> None:
        """Feed events into the global knowledge graph with ontology guidance."""
        if not COGNEE_AVAILABLE or not events:
            return

        await self._ensure_init()

        docs = []
        for ev in events:
            doc = (
                f"Event: {ev.title}\n"
                f"Source: {ev.source}\n"
                f"Venue: {ev.venue_name} at {ev.venue_address}\n"
                f"Time: {ev.start_time} to {ev.end_time}\n"
                f"Price: {ev.price}\n"
                f"Tags: {', '.join(ev.tags)}\n"
                f"Description: {ev.description[:500]}\n"
            )
            docs.append(doc)

        try:
            text_block = "\n---\n".join(docs)
            ontology_guided = f"{ONTOLOGY_PROMPT}\n\n---\nDATA TO PROCESS:\n\n{text_block}"
            await cognee.add(ontology_guided, dataset_name="events")
            log.info("cognee.ingested", count=len(docs))
            await cognee.cognify()
            log.info("cognee.cognified")
        except Exception as exc:
            log.error("cognee.ingest_error", error=str(exc))

    async def ingest_reviews(self, reviews: list[dict], venue_name: str) -> None:
        """Feed venue reviews into the global knowledge graph."""
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
        """Ingest raw training data (e.g. past event-planning chat logs)."""
        if not COGNEE_AVAILABLE or not text:
            return

        await self._ensure_init()

        try:
            await cognee.add(text, dataset_name=dataset_name)
            await cognee.cognify()
            log.info("cognee.training_ingested", dataset=dataset_name, chars=len(text))
        except Exception as exc:
            log.error("cognee.training_ingest_error", error=str(exc))

    # ------------------------------------------------------------------
    # Search — merged two-tier retrieval
    # ------------------------------------------------------------------

    async def search(
        self,
        query: str,
        user_id: str | None = None,
        template: str | None = None,
        template_kwargs: dict[str, str] | None = None,
    ) -> str:
        """
        Query the knowledge graph with optional user-personalized ranking.

        If a user_id is provided, the user's local KB augments the query
        and results are re-ranked with user preferences weighted higher.

        If a template name is given, the corresponding multi-hop query
        template is used instead of the raw query.
        """
        # Resolve template if specified
        if template and template in MULTI_HOP_TEMPLATES:
            query = get_query_template(template, **(template_kwargs or {}))

        # Record query in user KB
        user_kb = get_user_kb(user_id) if user_id else None
        if user_kb:
            user_kb.record_query(query)

        # Augment query with user preferences
        augmented_query = query
        if user_kb:
            pref_context = user_kb.get_preference_context()
            if pref_context:
                augmented_query = f"{query}\n\nUser preferences:\n{pref_context}"

        # Global search via Cognee
        global_results = await self._global_search(augmented_query)

        # Merge and rank
        if user_kb and global_results:
            return self._merge_results(global_results, user_kb)

        return global_results

    async def _global_search(self, query: str) -> str:
        """Query the global Cognee knowledge graph."""
        if not COGNEE_AVAILABLE:
            return ""

        await self._ensure_init()

        try:
            results = await cognee.search(query)
            log.info("cognee.search", query=query[:80], results=len(results) if results else 0)

            if not results:
                return ""

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

    def _merge_results(self, global_text: str, user_kb: UserKnowledgeBase) -> str:
        """
        Merge global results with user-local context.

        User preferences are appended with a weight marker so the LLM
        knows to prioritize them.
        """
        pref_context = user_kb.get_preference_context()
        if not pref_context:
            return global_text

        return (
            f"## Global Knowledge (weight: {self.GLOBAL_WEIGHT})\n"
            f"{global_text}\n\n"
            f"## Your Personal Context (weight: {self.USER_WEIGHT})\n"
            f"{pref_context}\n\n"
            f"NOTE: Personal context should be weighted {self.USER_WEIGHT}x "
            f"higher than global when ranking recommendations."
        )

    # ------------------------------------------------------------------
    # Feedback loop
    # ------------------------------------------------------------------

    async def record_event_chosen(self, user_id: str, event: Event) -> None:
        """User chose this event — positive signal."""
        kb = get_user_kb(user_id)
        kb.record_feedback(event, "chosen", 1.0)
        log.info("feedback.chosen", user=user_id, event_id=event.id)
        await self._feed_back_to_global(event, "chosen")

    async def record_event_skipped(self, user_id: str, event: Event) -> None:
        """User skipped this event — mild negative signal."""
        kb = get_user_kb(user_id)
        kb.record_feedback(event, "skipped", 0.0)
        log.info("feedback.skipped", user=user_id, event_id=event.id)

    async def record_event_rated(self, user_id: str, event: Event, rating: float) -> None:
        """User explicitly rated this event (1-5)."""
        kb = get_user_kb(user_id)
        kb.record_feedback(event, "rated", rating)
        log.info("feedback.rated", user=user_id, event_id=event.id, rating=rating)
        await self._feed_back_to_global(event, "rated", rating)

    async def _feed_back_to_global(
        self, event: Event, action: str, value: float = 0.0
    ) -> None:
        """Feed significant signals back into the global KB for all users."""
        if not COGNEE_AVAILABLE:
            return

        if action == "chosen" or (action == "rated" and value >= 4.0):
            feedback_text = (
                f"User feedback: {event.title} at {event.venue_name} "
                f"was {'chosen' if action == 'chosen' else f'rated {value}/5'}. "
                f"Tags: {', '.join(event.tags)}. "
                f"This event resonates with users."
            )
            try:
                await cognee.add(feedback_text, dataset_name="feedback")
                log.info("cognee.feedback_added", event=event.id, action=action)
            except Exception as exc:
                log.error("cognee.feedback_error", error=str(exc))

    # ------------------------------------------------------------------
    # Memory consolidation
    # ------------------------------------------------------------------

    async def remember(self) -> None:
        """Persist learned patterns (memify) for future sessions."""
        if not COGNEE_AVAILABLE:
            return

        try:
            await cognee.memify()
            log.info("cognee.memified")
        except Exception as exc:
            log.error("cognee.memify_error", error=str(exc))

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def get_user_stats(self, user_id: str) -> dict[str, Any]:
        """Return stats about a user's local KB."""
        kb = get_user_kb(user_id)
        return {
            "user_id": user_id,
            "queries": len(kb.query_history),
            "feedback_count": len(kb.feedback),
            "preferred_tags": len(kb.preferred_tags),
            "avoided_tags": len(kb.avoided_tags),
            "preferred_venues": len(kb.preferred_venues),
        }


# Backward-compatible alias
CogneeEngine = TwoTierCogneeEngine
