"""Tests for authentication module."""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock


class TestIsConfigured:
    def test_true_when_both_set(self):
        with patch("app.auth.settings") as m:
            m.supabase_url = "https://x.supabase.co"
            m.supabase_key = "key"
            from app.auth import is_configured
            assert is_configured() is True

    def test_false_when_url_empty(self):
        with patch("app.auth.settings") as m:
            m.supabase_url = ""
            m.supabase_key = "key"
            from app.auth import is_configured
            assert is_configured() is False

    def test_false_when_key_empty(self):
        with patch("app.auth.settings") as m:
            m.supabase_url = "https://x.supabase.co"
            m.supabase_key = ""
            from app.auth import is_configured
            assert is_configured() is False


class TestSignUpEmail:
    def test_returns_error_when_not_configured(self):
        with patch("app.auth._create_client", return_value=None):
            from app.auth import sign_up_email
            result = sign_up_email("a@b.com", "password")
            assert result == {"error": "Supabase not configured"}

    def test_success(self):
        mock_user = MagicMock()
        mock_user.id = "uid-123"
        mock_user.email = "a@b.com"
        mock_user.user_metadata = {"full_name": "Test User"}

        mock_session = MagicMock()
        mock_session.access_token = "at"
        mock_session.refresh_token = "rt"
        mock_session.expires_at = 9999

        mock_resp = MagicMock()
        mock_resp.user = mock_user
        mock_resp.session = mock_session

        mock_client = MagicMock()
        mock_client.auth.sign_up.return_value = mock_resp

        with patch("app.auth._create_client", return_value=mock_client):
            from app.auth import sign_up_email
            result = sign_up_email("a@b.com", "password")
            assert result["user"]["id"] == "uid-123"
            assert result["user"]["email"] == "a@b.com"
            assert result["session"]["access_token"] == "at"

    def test_already_registered(self):
        mock_client = MagicMock()
        mock_client.auth.sign_up.side_effect = Exception("User already registered")

        with patch("app.auth._create_client", return_value=mock_client):
            from app.auth import sign_up_email
            result = sign_up_email("a@b.com", "password")
            assert "already registered" in result["error"]


class TestSignInEmail:
    def test_returns_error_when_not_configured(self):
        with patch("app.auth._create_client", return_value=None):
            from app.auth import sign_in_email
            result = sign_in_email("a@b.com", "password")
            assert result == {"error": "Supabase not configured"}

    def test_success(self):
        mock_user = MagicMock()
        mock_user.id = "uid-456"
        mock_user.email = "a@b.com"
        mock_user.user_metadata = {}

        mock_session = MagicMock()
        mock_session.access_token = "at2"
        mock_session.refresh_token = "rt2"
        mock_session.expires_at = 1234

        mock_resp = MagicMock()
        mock_resp.user = mock_user
        mock_resp.session = mock_session

        mock_client = MagicMock()
        mock_client.auth.sign_in_with_password.return_value = mock_resp

        with patch("app.auth._create_client", return_value=mock_client):
            from app.auth import sign_in_email
            result = sign_in_email("a@b.com", "password")
            assert result["user"]["id"] == "uid-456"
            assert result["session"]["refresh_token"] == "rt2"


class TestExchangeOAuthCode:
    def test_returns_error_when_not_configured(self):
        with patch("app.auth._create_client", return_value=None):
            from app.auth import exchange_oauth_code
            result = exchange_oauth_code("some-code")
            assert result == {"error": "Supabase not configured"}


class TestGetAuthenticatedClient:
    def test_returns_none_when_not_configured(self):
        with patch("app.auth._create_client", return_value=None):
            from app.auth import get_authenticated_client
            result = get_authenticated_client("at", "rt")
            assert result is None

    def test_sets_session_on_client(self):
        mock_client = MagicMock()
        with patch("app.auth._create_client", return_value=mock_client):
            from app.auth import get_authenticated_client
            result = get_authenticated_client("at", "rt")
            mock_client.auth.set_session.assert_called_once_with("at", "rt")
            assert result is mock_client


class TestRefreshSession:
    def test_returns_error_when_not_configured(self):
        with patch("app.auth._create_client", return_value=None):
            from app.auth import refresh_session
            result = refresh_session("rt")
            assert result == {"error": "Supabase not configured"}


class TestExtractHelpers:
    def test_extract_user(self):
        from app.auth import _extract_user
        mock_user = MagicMock()
        mock_user.id = "uid"
        mock_user.email = "test@example.com"
        mock_user.user_metadata = {"full_name": "Jane Doe"}
        result = _extract_user(mock_user)
        assert result == {"id": "uid", "email": "test@example.com", "display_name": "Jane Doe"}

    def test_extract_user_no_name(self):
        from app.auth import _extract_user
        mock_user = MagicMock()
        mock_user.id = "uid"
        mock_user.email = "test@example.com"
        mock_user.user_metadata = {}
        result = _extract_user(mock_user)
        assert result["display_name"] == ""

    def test_extract_session(self):
        from app.auth import _extract_session
        mock_session = MagicMock()
        mock_session.access_token = "at"
        mock_session.refresh_token = "rt"
        mock_session.expires_at = 1000
        result = _extract_session(mock_session)
        assert result == {"access_token": "at", "refresh_token": "rt", "expires_at": 1000}
