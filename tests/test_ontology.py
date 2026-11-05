"""Tests for knowledge/ontology.py — entity types, relationships, and query templates."""
from __future__ import annotations

import pytest

from knowledge.ontology import (
    EventEntity,
    VenueEntity,
    ReviewEntity,
    PatternEntity,
    Relationship,
    MULTI_HOP_TEMPLATES,
    ONTOLOGY_PROMPT,
    ALL_ENTITY_TYPES,
    ALL_RELATIONSHIPS,
    get_query_template,
)


# ---------------------------------------------------------------------------
# Entity types
# ---------------------------------------------------------------------------

class TestEventEntity:
    def test_defaults(self):
        e = EventEntity()
        assert e.name == ""
        assert e.vibes == []
        assert e.tags == []

    def test_with_fields(self):
        e = EventEntity(
            name="Jazz Night",
            event_type="concert",
            vibes=["chill", "intimate"],
            crowd_type="young-professionals",
            age_appeal="30s",
            noise_level="moderate",
            formality="smart-casual",
            group_size="couples",
        )
        assert e.name == "Jazz Night"
        assert "chill" in e.vibes
        assert e.crowd_type == "young-professionals"

    def test_tags_are_independent(self):
        e1 = EventEntity(tags=["jazz"])
        e2 = EventEntity()
        assert e1.tags == ["jazz"]
        assert e2.tags == []


class TestVenueEntity:
    def test_defaults(self):
        v = VenueEntity()
        assert v.transit_friendly is False
        assert v.outdoor_space is False
        assert v.ambiance == []

    def test_with_fields(self):
        v = VenueEntity(
            name="The Blue Note",
            venue_type="bar",
            neighborhood="Mission",
            capacity="medium",
            ambiance=["cozy", "trendy"],
            price_tier="$$",
            transit_friendly=True,
        )
        assert v.name == "The Blue Note"
        assert v.transit_friendly is True
        assert "trendy" in v.ambiance


class TestReviewEntity:
    def test_defaults(self):
        r = ReviewEntity()
        assert r.rating == 0.0
        assert r.mentioned_vibes == []

    def test_with_fields(self):
        r = ReviewEntity(
            text="Great for date night",
            rating=4.5,
            sentiment="positive",
            recommended_for="dates",
        )
        assert r.rating == 4.5
        assert r.recommended_for == "dates"


class TestPatternEntity:
    def test_defaults(self):
        p = PatternEntity()
        assert p.confidence == 0.0
        assert p.peak_times == []

    def test_with_fields(self):
        p = PatternEntity(
            pattern_type="crowd-shift",
            description="20s crowd before 10pm, 30s after",
            confidence=0.8,
            demographic_shift="20s → 30s after 10pm",
        )
        assert p.confidence == 0.8
        assert "crowd-shift" == p.pattern_type


# ---------------------------------------------------------------------------
# Relationships
# ---------------------------------------------------------------------------

class TestRelationships:
    def test_count(self):
        assert len(Relationship) == 15

    def test_values(self):
        assert Relationship.HOSTED_AT.value == "hosted_at"
        assert Relationship.NEARBY.value == "nearby"
        assert Relationship.FOLLOWED_BY.value == "followed_by"
        assert Relationship.COMPETES_WITH.value == "competes_with"

    def test_all_relationships_list(self):
        assert len(ALL_RELATIONSHIPS) == 15
        assert Relationship.HOSTED_AT in ALL_RELATIONSHIPS


# ---------------------------------------------------------------------------
# Multi-hop query templates
# ---------------------------------------------------------------------------

class TestQueryTemplates:
    def test_count(self):
        assert len(MULTI_HOP_TEMPLATES) == 6

    def test_template_names(self):
        expected = {
            "age_personalized",
            "solo_friendly",
            "date_night",
            "group_outing",
            "hidden_gems",
            "neighborhood_crawl",
        }
        assert set(MULTI_HOP_TEMPLATES.keys()) == expected

    def test_get_query_template_with_kwargs(self):
        result = get_query_template("neighborhood_crawl", neighborhood="Mission")
        assert "Mission" in result

    def test_get_query_template_missing_kwargs(self):
        result = get_query_template("age_personalized")
        assert result  # returns template with unfilled placeholders
        assert "age_bracket" in result or "{" in result

    def test_get_query_template_unknown(self):
        result = get_query_template("nonexistent_template")
        assert result == ""


# ---------------------------------------------------------------------------
# Ontology prompt
# ---------------------------------------------------------------------------

class TestOntologyPrompt:
    def test_prompt_not_empty(self):
        assert len(ONTOLOGY_PROMPT) > 100

    def test_prompt_mentions_entity_types(self):
        assert "EventEntity" in ONTOLOGY_PROMPT
        assert "VenueEntity" in ONTOLOGY_PROMPT
        assert "ReviewEntity" in ONTOLOGY_PROMPT
        assert "PatternEntity" in ONTOLOGY_PROMPT

    def test_prompt_mentions_relationships(self):
        assert "hosted_at" in ONTOLOGY_PROMPT
        assert "similar_crowd" in ONTOLOGY_PROMPT
        assert "nearby" in ONTOLOGY_PROMPT

    def test_all_entity_types_list(self):
        assert len(ALL_ENTITY_TYPES) == 4
