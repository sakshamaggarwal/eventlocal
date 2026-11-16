"""
Affiliate / referral link builder.

Appends source-specific tracking parameters to event URLs when an
affiliate ID is configured, so eventlocal can earn commission on
referred ticket sales.

Supported programs:
- Ticketmaster — CJ Affiliate (``camefrom`` param)
- SeatGeek — Partner Program (``aid`` param)
- Eventbrite — Affiliate Program (``aff`` param)
"""
from __future__ import annotations

from urllib.parse import urlencode, urlparse, parse_qs, urlunparse

from app.config import settings


_SOURCE_PARAM_MAP: dict[str, tuple[str, str]] = {
    "ticketmaster": ("camefrom", "ticketmaster_affiliate_id"),
    "seatgeek": ("aid", "seatgeek_partner_id"),
    "eventbrite": ("aff", "eventbrite_affiliate_id"),
}


def get_affiliate_url(url: str, source: str) -> str:
    """Return *url* with the affiliate tracking parameter appended.

    If no affiliate ID is configured for *source*, or the URL is empty,
    the original URL is returned unchanged.
    """
    if not url:
        return url

    mapping = _SOURCE_PARAM_MAP.get(source)
    if mapping is None:
        return url

    param_name, settings_attr = mapping
    affiliate_id = getattr(settings, settings_attr, "")
    if not affiliate_id:
        return url

    parsed = urlparse(url)
    qs = parse_qs(parsed.query, keep_blank_values=True)
    qs[param_name] = [affiliate_id]
    new_query = urlencode(qs, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


def has_affiliate(source: str) -> bool:
    """Return True if an affiliate ID is set for *source*."""
    mapping = _SOURCE_PARAM_MAP.get(source)
    if mapping is None:
        return False
    _, settings_attr = mapping
    return bool(getattr(settings, settings_attr, ""))
