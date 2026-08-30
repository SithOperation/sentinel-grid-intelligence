"""Canonical public URLs used before source-feed identity and deduplication."""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_KEYS = {
    "fbclid",
    "gclid",
    "share_id",
    "utm_campaign",
    "utm_content",
    "utm_medium",
    "utm_name",
    "utm_source",
    "utm_term",
    "mc_cid",
    "mc_eid",
    "ref",
}


def canonicalize_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username:
        raise ValueError("source item URL must be a public HTTP(S) URL")
    host = parsed.netloc.casefold()
    if host in {"twitter.com", "www.twitter.com", "www.x.com", "mobile.x.com"}:
        host = "x.com"
    elif host in {"old.reddit.com", "new.reddit.com", "www.reddit.com"}:
        host = "reddit.com"
    elif host in {"www.reuters.com", "mobile.reuters.com"}:
        host = "reuters.com"
    path = parsed.path.rstrip("/") or "/"
    query = urlencode(
        [
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if key.casefold() not in TRACKING_KEYS
        ]
    )
    return urlunsplit(("https", host, path, query, ""))
