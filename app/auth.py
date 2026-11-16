"""
Supabase authentication — email + Google OAuth.

Gracefully no-ops when SUPABASE_URL is not configured.
Uses a Streamlit-compatible storage adapter so the PKCE OAuth flow
survives page reloads (the code_verifier is kept in session_state).
"""
from __future__ import annotations

from typing import Any

import structlog

from app.config import settings

log = structlog.get_logger()


# ---------------------------------------------------------------------------
# Streamlit-compatible session storage for gotrue PKCE flow
# ---------------------------------------------------------------------------

class StreamlitSessionStorage:
    """Storage adapter backed by Streamlit session_state.

    gotrue-py stores the PKCE code_verifier and session tokens here.
    Because session_state survives Streamlit reruns (and OAuth redirects
    within the same browser session), the verifier is available when
    the user returns from Google sign-in.
    """

    def get_item(self, key: str) -> str | None:
        import streamlit as st
        return st.session_state.get(f"_supa_{key}")

    def set_item(self, key: str, value: str) -> None:
        import streamlit as st
        st.session_state[f"_supa_{key}"] = value

    def remove_item(self, key: str) -> None:
        import streamlit as st
        st.session_state.pop(f"_supa_{key}", None)


# ---------------------------------------------------------------------------
# Client factory
# ---------------------------------------------------------------------------

def _create_client(storage=None):
    """Create a Supabase client, optionally with custom storage."""
    if not settings.supabase_url or not settings.supabase_key:
        return None
    try:
        from supabase import create_client

        if storage is not None:
            try:
                from supabase import ClientOptions
                return create_client(
                    settings.supabase_url,
                    settings.supabase_key,
                    options=ClientOptions(storage=storage, flow_type="pkce"),
                )
            except (ImportError, TypeError):
                pass

        return create_client(settings.supabase_url, settings.supabase_key)
    except Exception as exc:
        log.error("auth.client_error", error=str(exc))
        return None


def is_configured() -> bool:
    """Check whether Supabase credentials are set."""
    return bool(settings.supabase_url and settings.supabase_key)


# ---------------------------------------------------------------------------
# Email auth
# ---------------------------------------------------------------------------

def sign_up_email(email: str, password: str) -> dict[str, Any]:
    """Sign up with email and password. Returns user + session or error."""
    client = _create_client()
    if not client:
        return {"error": "Supabase not configured"}
    try:
        resp = client.auth.sign_up({"email": email, "password": password})
        if resp.user:
            session_data = _extract_session(resp.session) if resp.session else None
            return {
                "user": _extract_user(resp.user),
                "session": session_data,
            }
        return {"error": "Sign-up failed — check your email and password"}
    except Exception as exc:
        msg = str(exc)
        if "already registered" in msg.lower():
            return {"error": "This email is already registered. Try signing in."}
        return {"error": msg}


def sign_in_email(email: str, password: str) -> dict[str, Any]:
    """Sign in with email and password. Returns user + session or error."""
    client = _create_client()
    if not client:
        return {"error": "Supabase not configured"}
    try:
        resp = client.auth.sign_in_with_password({"email": email, "password": password})
        if resp.user and resp.session:
            return {
                "user": _extract_user(resp.user),
                "session": _extract_session(resp.session),
            }
        return {"error": "Invalid email or password"}
    except Exception as exc:
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Google OAuth (PKCE flow)
# ---------------------------------------------------------------------------

def get_google_oauth_url(redirect_url: str) -> str | None:
    """Generate Google OAuth URL for the PKCE redirect flow.

    The returned URL sends the user to Google sign-in. After auth,
    Google redirects back to *redirect_url* with ``?code=...`` in the
    query string. Call :func:`exchange_oauth_code` with that code.
    """
    storage = StreamlitSessionStorage()
    client = _create_client(storage=storage)
    if not client:
        return None
    try:
        resp = client.auth.sign_in_with_oauth({
            "provider": "google",
            "options": {"redirect_to": redirect_url},
        })
        return resp.url if hasattr(resp, "url") else None
    except Exception as exc:
        log.error("auth.google_oauth_error", error=str(exc))
        return None


def exchange_oauth_code(code: str) -> dict[str, Any]:
    """Exchange an OAuth authorization code for a session (PKCE callback)."""
    storage = StreamlitSessionStorage()
    client = _create_client(storage=storage)
    if not client:
        return {"error": "Supabase not configured"}
    try:
        resp = client.auth.exchange_code_for_session({"auth_code": code})
        if resp.user and resp.session:
            return {
                "user": _extract_user(resp.user),
                "session": _extract_session(resp.session),
            }
        return {"error": "OAuth code exchange failed"}
    except Exception as exc:
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------

def get_authenticated_client(access_token: str, refresh_token: str):
    """Return a Supabase client carrying the user's JWT for RLS queries."""
    client = _create_client()
    if not client:
        return None
    try:
        client.auth.set_session(access_token, refresh_token)
        return client
    except Exception as exc:
        log.error("auth.set_session_error", error=str(exc))
        return None


def refresh_session(refresh_token: str) -> dict[str, Any]:
    """Refresh an expired access token."""
    client = _create_client()
    if not client:
        return {"error": "Supabase not configured"}
    try:
        resp = client.auth.refresh_session(refresh_token)
        if resp.user and resp.session:
            return {
                "user": _extract_user(resp.user),
                "session": _extract_session(resp.session),
            }
        return {"error": "Session refresh failed"}
    except Exception as exc:
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_user(user) -> dict[str, Any]:
    return {
        "id": str(user.id),
        "email": user.email or "",
        "display_name": (
            (user.user_metadata or {}).get("full_name")
            or (user.user_metadata or {}).get("name")
            or ""
        ),
    }


def _extract_session(session) -> dict[str, Any]:
    return {
        "access_token": session.access_token,
        "refresh_token": session.refresh_token,
        "expires_at": getattr(session, "expires_at", 0),
    }
