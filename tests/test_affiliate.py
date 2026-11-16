"""Tests for utils.affiliate — affiliate / referral link builder."""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from utils.affiliate import get_affiliate_url, has_affiliate


# ---------------------------------------------------------------------------
# Helpers — patch settings attrs in-place for each test
# ---------------------------------------------------------------------------

def _patch_settings(**overrides):
    """Return a patch context-manager for app.config.settings attributes."""
    from app.config import settings
    return patch.multiple(settings, **overrides)


# ---------------------------------------------------------------------------
# get_affiliate_url
# ---------------------------------------------------------------------------

class TestGetAffiliateUrl:
    def test_ticketmaster_appends_param(self):
        with _patch_settings(ticketmaster_affiliate_id="TM_AFF_123"):
            result = get_affiliate_url(
                "https://www.ticketmaster.com/event/abc",
                "ticketmaster",
            )
            assert "camefrom=TM_AFF_123" in result
            assert result.startswith("https://www.ticketmaster.com/event/abc")

    def test_seatgeek_appends_param(self):
        with _patch_settings(seatgeek_partner_id="SG_PARTNER_456"):
            result = get_affiliate_url(
                "https://seatgeek.com/some-event",
                "seatgeek",
            )
            assert "aid=SG_PARTNER_456" in result

    def test_eventbrite_appends_param(self):
        with _patch_settings(eventbrite_affiliate_id="EB_AFF_789"):
            result = get_affiliate_url(
                "https://www.eventbrite.com/e/my-event-12345",
                "eventbrite",
            )
            assert "aff=EB_AFF_789" in result

    def test_no_affiliate_id_returns_original(self):
        with _patch_settings(ticketmaster_affiliate_id=""):
            result = get_affiliate_url(
                "https://www.ticketmaster.com/event/abc",
                "ticketmaster",
            )
            assert result == "https://www.ticketmaster.com/event/abc"

    def test_unknown_source_returns_original(self):
        url = "https://lu.ma/some-event"
        assert get_affiliate_url(url, "luma") == url
        assert get_affiliate_url(url, "google_places") == url

    def test_empty_url_returns_empty(self):
        with _patch_settings(ticketmaster_affiliate_id="TM_123"):
            assert get_affiliate_url("", "ticketmaster") == ""

    def test_preserves_existing_query_params(self):
        with _patch_settings(seatgeek_partner_id="SG_1"):
            result = get_affiliate_url(
                "https://seatgeek.com/event?foo=bar",
                "seatgeek",
            )
            assert "foo=bar" in result
            assert "aid=SG_1" in result

    def test_does_not_duplicate_param_on_repeat_call(self):
        with _patch_settings(ticketmaster_affiliate_id="TM_1"):
            url1 = get_affiliate_url("https://ticketmaster.com/e/1", "ticketmaster")
            url2 = get_affiliate_url(url1, "ticketmaster")
            assert url2.count("camefrom=") == 1


# ---------------------------------------------------------------------------
# has_affiliate
# ---------------------------------------------------------------------------

class TestHasAffiliate:
    def test_true_when_configured(self):
        with _patch_settings(ticketmaster_affiliate_id="TM_1"):
            assert has_affiliate("ticketmaster") is True

    def test_false_when_empty(self):
        with _patch_settings(ticketmaster_affiliate_id=""):
            assert has_affiliate("ticketmaster") is False

    def test_false_for_unknown_source(self):
        assert has_affiliate("luma") is False
        assert has_affiliate("google_places") is False
        assert has_affiliate("yelp") is False
