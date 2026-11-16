"""Tests for all event source clients."""
from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from models.user_profile import Event
from sources.ticketmaster_client import TicketmasterClient
from sources.seatgeek_client import SeatGeekClient
from sources.luma_client import LumaClient
from sources.eventbrite_client import EventbriteClient
from sources.google_places_client import GooglePlacesClient


# ---- Ticketmaster ----

class TestTicketmasterClient:
    @pytest.mark.asyncio
    async def test_skips_without_api_key(self):
        with patch("sources.ticketmaster_client.settings") as mock:
            mock.ticketmaster_api_key = ""
            client = TicketmasterClient()
            result = await client.fetch_events("bay-area", "2026-11-05")
            assert result == []

    @pytest.mark.asyncio
    async def test_parses_response(self):
        fake_response = {
            "_embedded": {
                "events": [
                    {
                        "id": "tm-1",
                        "name": "Rock Concert",
                        "info": "A great show",
                        "url": "https://ticketmaster.com/ev/1",
                        "dates": {"start": {"dateTime": "2026-11-05T20:00:00Z", "localDate": "2026-11-05"}},
                        "classifications": [
                            {"genre": {"name": "Rock"}, "subGenre": {"name": "Alternative"}, "segment": {"name": "Music"}}
                        ],
                        "priceRanges": [{"min": 25, "max": 75}],
                        "_embedded": {
                            "venues": [{
                                "name": "The Fillmore",
                                "address": {"line1": "1805 Geary Blvd"},
                                "city": {"name": "San Francisco"},
                                "state": {"stateCode": "CA"},
                                "location": {"latitude": "37.784", "longitude": "-122.433"},
                            }]
                        },
                        "images": [{"url": "https://img.example.com/rock.jpg"}],
                    }
                ]
            }
        }

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = fake_response

        with patch("sources.ticketmaster_client.settings") as mock_settings:
            mock_settings.ticketmaster_api_key = "test-key"
            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.get.return_value = mock_resp
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client_cls.return_value = mock_client

                client = TicketmasterClient()
                events = await client.fetch_events("bay-area", "2026-11-05")

        assert len(events) == 1
        ev = events[0]
        assert ev.title == "Rock Concert"
        assert ev.source == "ticketmaster"
        assert ev.venue_name == "The Fillmore"
        assert "rock" in ev.tags
        assert ev.price == "$25-$75"

    @pytest.mark.asyncio
    async def test_handles_api_error(self):
        with patch("sources.ticketmaster_client.settings") as mock_settings:
            mock_settings.ticketmaster_api_key = "test-key"
            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.get.side_effect = Exception("Connection failed")
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client_cls.return_value = mock_client

                client = TicketmasterClient()
                result = await client.fetch_events("bay-area", "2026-11-05")
                assert result == []


# ---- SeatGeek ----

class TestSeatGeekClient:
    @pytest.mark.asyncio
    async def test_skips_without_client_id(self):
        with patch("sources.seatgeek_client.settings") as mock:
            mock.seatgeek_client_id = ""
            client = SeatGeekClient()
            result = await client.fetch_events("bay-area", "2026-11-05")
            assert result == []

    @pytest.mark.asyncio
    async def test_parses_response(self):
        fake_response = {
            "events": [
                {
                    "id": 12345,
                    "title": "Warriors vs Lakers",
                    "short_title": "Warriors vs Lakers",
                    "type": "nba",
                    "url": "https://seatgeek.com/warriors-lakers",
                    "datetime_utc": "2026-11-05T19:30:00",
                    "datetime_local": "2026-11-05T11:30:00",
                    "venue": {
                        "name": "Chase Center",
                        "name_v2": "Chase Center",
                        "display_location": "San Francisco, CA",
                        "address": "1 Warriors Way",
                        "lat": 37.768,
                        "lon": -122.387,
                        "location": {"lat": 37.768, "lon": -122.387},
                    },
                    "performers": [
                        {"name": "Golden State Warriors", "type": "nba", "genres": [{"slug": "basketball"}], "image": "https://img.example.com/gsw.jpg"},
                        {"name": "Los Angeles Lakers", "type": "nba", "genres": []},
                    ],
                    "stats": {"lowest_price": 45, "highest_price": 500, "listing_count": 200},
                }
            ]
        }

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = fake_response

        with patch("sources.seatgeek_client.settings") as mock_settings:
            mock_settings.seatgeek_client_id = "test-id"
            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.get.return_value = mock_resp
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client_cls.return_value = mock_client

                client = SeatGeekClient()
                events = await client.fetch_events("bay-area", "2026-11-05")

        assert len(events) == 1
        ev = events[0]
        assert ev.title == "Warriors vs Lakers"
        assert ev.source == "seatgeek"
        assert ev.venue_name == "Chase Center"
        assert "$45-$500" in ev.price
        assert "nba" in ev.tags

    @pytest.mark.asyncio
    async def test_handles_api_error(self):
        with patch("sources.seatgeek_client.settings") as mock_settings:
            mock_settings.seatgeek_client_id = "test-id"
            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.get.side_effect = Exception("Network error")
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client_cls.return_value = mock_client

                client = SeatGeekClient()
                result = await client.fetch_events("bay-area", "2026-11-05")
                assert result == []


# ---- Existing sources (basic contract tests) ----

class TestExistingSources:
    @pytest.mark.asyncio
    async def test_luma_skips_without_key(self):
        with patch("sources.luma_client.settings") as mock:
            mock.luma_api_key = ""
            client = LumaClient()
            assert await client.fetch_events("bay-area", "2026-11-05") == []

    @pytest.mark.asyncio
    async def test_eventbrite_skips_without_key(self):
        with patch("sources.eventbrite_client.settings") as mock:
            mock.eventbrite_api_key = ""
            client = EventbriteClient()
            assert await client.fetch_events("bay-area", "2026-11-05") == []

    @pytest.mark.asyncio
    async def test_google_places_skips_without_key(self):
        with patch("sources.google_places_client.settings") as mock:
            mock.google_places_api_key = ""
            client = GooglePlacesClient()
            assert await client.fetch_events("bay-area", "2026-11-05") == []


# ---- Source interface contract ----

class TestSourceInterface:
    def test_all_sources_have_name(self):
        sources = [
            LumaClient(),
            EventbriteClient(),
            GooglePlacesClient(),
            TicketmasterClient(),
            SeatGeekClient(),
        ]
        names = {s.name for s in sources}
        assert len(names) == 5
        assert "ticketmaster" in names
        assert "seatgeek" in names

    def test_source_names_unique(self):
        sources = [
            LumaClient(),
            EventbriteClient(),
            GooglePlacesClient(),
            TicketmasterClient(),
            SeatGeekClient(),
        ]
        names = [s.name for s in sources]
        assert len(names) == len(set(names))
