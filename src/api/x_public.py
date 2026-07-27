"""Bounded, unauthenticated retrieval of explicitly configured public X posts."""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin

import requests

from models.x_report import canonical_x_url

USER_AGENT = (
    "SentinelGridIntelligence/1.0 "
    "(public-status-metadata collector; contact: repository maintainers)"
)


class XCollectionError(RuntimeError):
    """Base error for one public-status acquisition."""


class XUnavailableError(XCollectionError):
    """The configured public post is unavailable without authentication."""


class XFetchError(XCollectionError):
    """The public page could not be retrieved safely."""


class XMetadataError(XCollectionError):
    """The public page did not contain valid stable post metadata."""


@dataclass(frozen=True, slots=True)
class PublicPage:
    requested_url: str
    final_url: str
    html: str


@dataclass(frozen=True, slots=True)
class PublicPost:
    status_id: str
    canonical_url: str
    account: str
    text: str
    published_at: str


class PublicXTransport:
    """Fetch HTML with bounded redirects, timeouts, and response size."""

    def __init__(
        self,
        *,
        connect_timeout_seconds: float = 5,
        read_timeout_seconds: float = 10,
        max_response_bytes: int = 1_000_000,
        session: Any | None = None,
    ) -> None:
        if connect_timeout_seconds <= 0 or read_timeout_seconds <= 0:
            raise ValueError("X request timeouts must be positive")
        if max_response_bytes < 1024:
            raise ValueError("X maximum response size is too small")
        self.connect_timeout_seconds = connect_timeout_seconds
        self.read_timeout_seconds = read_timeout_seconds
        self.max_response_bytes = max_response_bytes
        self.session = session or requests.Session()

    def fetch(self, url: str) -> PublicPage:
        canonical, _, configured_status_id = canonical_x_url(url)
        current_url = canonical
        response: requests.Response | None = None
        for _ in range(6):
            try:
                response = self.session.get(
                    current_url,
                    headers={
                        "User-Agent": USER_AGENT,
                        "Accept": "text/html,application/xhtml+xml",
                    },
                    timeout=(
                        self.connect_timeout_seconds,
                        self.read_timeout_seconds,
                    ),
                    allow_redirects=False,
                    stream=True,
                )
            except requests.Timeout as error:
                raise XFetchError("request timed out") from error
            except requests.RequestException as error:
                raise XFetchError(f"request failed: {error}") from error
            assert response is not None
            if response.status_code not in {301, 302, 303, 307, 308}:
                break
            location = response.headers.get("Location")
            response.close()
            if not location:
                raise XFetchError("redirect response is missing a destination")
            destination = urljoin(current_url, location)
            try:
                current_url, _, redirect_status_id = canonical_x_url(destination)
            except ValueError as error:
                raise XFetchError(
                    "redirect destination is outside a public X status URL"
                ) from error
            if redirect_status_id != configured_status_id:
                raise XFetchError("redirect changed the configured X status ID")
        else:
            raise XFetchError("too many redirects")

        assert response is not None
        try:
            try:
                final_url, _, final_status_id = canonical_x_url(response.url)
            except ValueError as error:
                raise XFetchError(
                    "redirect destination is outside a public X status URL"
                ) from error
            if final_status_id != configured_status_id:
                raise XFetchError("redirect changed the configured X status ID")
            if response.status_code in {401, 403, 404, 410}:
                raise XUnavailableError(
                    f"public post is unavailable (HTTP {response.status_code})"
                )
            if response.status_code < 200 or response.status_code >= 300:
                raise XFetchError(f"request failed with HTTP {response.status_code}")
            content_type = response.headers.get("Content-Type", "").casefold()
            if (
                "text/html" not in content_type
                and "application/xhtml+xml" not in content_type
            ):
                raise XFetchError("response is not HTML")
            declared = response.headers.get("Content-Length")
            if declared:
                try:
                    if int(declared) > self.max_response_bytes:
                        raise XFetchError("response exceeds configured size limit")
                except ValueError as error:
                    raise XFetchError(
                        "response has an invalid Content-Length"
                    ) from error
            body = bytearray()
            try:
                for chunk in response.iter_content(chunk_size=16_384):
                    body.extend(chunk)
                    if len(body) > self.max_response_bytes:
                        raise XFetchError("response exceeds configured size limit")
            except requests.Timeout as error:
                raise XFetchError("response read timed out") from error
            except requests.RequestException as error:
                raise XFetchError(f"response read failed: {error}") from error
            encoding = response.encoding or "utf-8"
            try:
                html = bytes(body).decode(encoding)
            except (LookupError, UnicodeDecodeError) as error:
                raise XFetchError("response HTML encoding is invalid") from error
            return PublicPage(canonical, final_url, html)
        finally:
            response.close()


class _MetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.json_ld: list[str] = []
        self._in_json_ld = False
        self._script_parts: list[str] = []
        self.visible_parts: list[str] = []
        self._hidden_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.casefold(): value for key, value in attrs if value is not None}
        if tag.casefold() == "meta":
            key = values.get("property") or values.get("name")
            content = values.get("content")
            if key and content is not None:
                self.meta[key.casefold()] = content
        if tag.casefold() == "script":
            self._hidden_depth += 1
            if values.get("type", "").casefold() == "application/ld+json":
                self._in_json_ld = True
                self._script_parts = []
        elif tag.casefold() in {"style", "noscript"}:
            self._hidden_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "script":
            if self._in_json_ld:
                self.json_ld.append("".join(self._script_parts))
                self._in_json_ld = False
            self._hidden_depth = max(0, self._hidden_depth - 1)
        elif tag.casefold() in {"style", "noscript"}:
            self._hidden_depth = max(0, self._hidden_depth - 1)

    def handle_data(self, data: str) -> None:
        if self._in_json_ld:
            self._script_parts.append(data)
        elif not self._hidden_depth and data.strip():
            self.visible_parts.append(data.strip())


def _walk_json(value: object) -> Iterator[Mapping[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_json(child)


def _author_handle(value: object) -> str | None:
    candidates: list[object]
    if isinstance(value, list):
        candidates = list(value)
    else:
        candidates = [value]
    for candidate in candidates:
        if isinstance(candidate, str):
            text = candidate
        elif isinstance(candidate, dict):
            text = str(candidate.get("alternateName") or candidate.get("name") or "")
        else:
            continue
        text = text.strip().lstrip("@")
        if text and len(text) <= 15 and text.replace("_", "").isalnum():
            return text
    return None


def extract_public_post(page: PublicPage) -> PublicPost:
    """Extract a post from JSON-LD/Open Graph without visual DOM selectors."""
    _, _, requested_id = canonical_x_url(page.requested_url)
    canonical, expected_account, expected_id = canonical_x_url(page.final_url)
    if expected_id != requested_id:
        raise XMetadataError("fetched page does not match configured status ID")
    parser = _MetadataParser()
    try:
        parser.feed(page.html)
    except Exception as error:
        raise XMetadataError("public page contains malformed HTML") from error

    availability_text = " ".join(
        [*parser.visible_parts, *parser.meta.values()]
    ).casefold()
    unavailable_markers = (
        "this post is unavailable",
        "this post was deleted",
        "account suspended",
        "sign in to x",
        "log in to x",
        "don’t miss what’s happening",
        "don't miss what's happening",
    )
    if any(marker in availability_text for marker in unavailable_markers):
        raise XUnavailableError("public post is deleted, unavailable, or login-gated")

    text: str | None = None
    published: str | None = None
    author: str | None = None
    metadata_url: str | None = None
    for raw in parser.json_ld:
        try:
            value = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue
        for item in _walk_json(value):
            candidate_text = item.get("articleBody") or item.get("text")
            candidate_time = item.get("datePublished") or item.get("dateCreated")
            if isinstance(candidate_text, str) and isinstance(candidate_time, str):
                text = candidate_text
                published = candidate_time
                author = _author_handle(item.get("author"))
                candidate_url = item.get("url") or item.get("mainEntityOfPage")
                if isinstance(candidate_url, str):
                    metadata_url = candidate_url
                break
        if text and published:
            break

    if text is None:
        text = parser.meta.get("og:description") or parser.meta.get(
            "twitter:description"
        )
    if published is None:
        published = parser.meta.get("article:published_time")
    metadata_url = metadata_url or parser.meta.get("og:url")
    author = author or _author_handle(parser.meta.get("twitter:creator"))

    if metadata_url:
        try:
            metadata_canonical, metadata_account, metadata_id = canonical_x_url(
                metadata_url
            )
        except ValueError as error:
            raise XMetadataError("metadata canonical URL is invalid") from error
        if (
            metadata_id != expected_id
            or metadata_account.casefold() != expected_account.casefold()
        ):
            raise XMetadataError(
                "metadata identity does not match configured status URL"
            )
        canonical = metadata_canonical
    if author and author.casefold() != expected_account.casefold():
        raise XMetadataError("metadata author does not match configured account")
    if not isinstance(text, str) or not unescape(text).strip():
        raise XMetadataError("public metadata is missing post text")
    if not isinstance(published, str) or not published.strip():
        raise XMetadataError("public metadata is missing publication timestamp")
    return PublicPost(
        status_id=expected_id,
        canonical_url=canonical,
        account=expected_account,
        text=unescape(text).strip(),
        published_at=published.strip(),
    )
