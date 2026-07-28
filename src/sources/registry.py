"""Strict loader for the versioned controlled-source registry."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import yaml

REGISTRY_VERSION = "1.0"
ADAPTERS = {"x", "reddit", "website", "rss", "manual_url"}
TRUST_TIERS = {"official", "publisher", "osint", "aggregator", "community"}
ALLOWED_FIELDS = {
    "id",
    "name",
    "adapter",
    "url",
    "enabled",
    "categories",
    "trust_tier",
    "default_feed_eligible",
    "allow_embedding",
    "maximum_items",
    "discovery_interval_minutes",
    "retention_hours",
    "expected_language",
    "geographic_scope",
    "owner",
}
_ID = re.compile(r"^[a-z][a-z0-9_]{2,63}$")


@dataclass(frozen=True, slots=True)
class SourceDefinition:
    id: str
    name: str
    adapter: str
    url: str
    enabled: bool
    categories: tuple[str, ...]
    trust_tier: str
    default_feed_eligible: bool
    allow_embedding: bool
    maximum_items: int
    discovery_interval_minutes: int
    retention_hours: int
    expected_language: str
    geographic_scope: str
    owner: str


@dataclass(frozen=True, slots=True)
class SourceRegistry:
    version: str
    sources: tuple[SourceDefinition, ...]


def _canonical_registry_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    if parsed.scheme != "https" or not parsed.netloc or parsed.username:
        raise ValueError("source registry URLs must be public HTTPS URLs")
    if parsed.query or parsed.fragment:
        raise ValueError(
            "source registry URLs cannot contain query strings or fragments"
        )
    host = parsed.netloc.casefold()
    path = parsed.path.rstrip("/")
    if host in {"twitter.com", "www.twitter.com", "www.x.com"}:
        host = "x.com"
    return f"https://{host}{path}"


def _source(value: object) -> SourceDefinition:
    if not isinstance(value, dict):
        raise TypeError("registry source must be an object")
    unknown = set(value).difference(ALLOWED_FIELDS)
    if unknown:
        raise ValueError(f"registry source has unknown fields: {sorted(unknown)}")
    required = ALLOWED_FIELDS
    missing = required.difference(value)
    if missing:
        raise ValueError(f"registry source missing fields: {sorted(missing)}")
    source_id = value["id"]
    if not isinstance(source_id, str) or _ID.fullmatch(source_id) is None:
        raise ValueError("registry source id is invalid")
    adapter = value["adapter"]
    if adapter not in ADAPTERS:
        raise ValueError("registry source adapter is unsupported")
    trust_tier = value["trust_tier"]
    if trust_tier not in TRUST_TIERS:
        raise ValueError("registry source trust tier is unsupported")
    categories = value["categories"]
    if (
        not isinstance(categories, list)
        or not categories
        or any(not isinstance(item, str) or not item for item in categories)
    ):
        raise ValueError("registry source categories are invalid")
    for field in ("enabled", "default_feed_eligible", "allow_embedding"):
        if not isinstance(value[field], bool):
            raise TypeError(f"registry source {field} must be boolean")
    for field in (
        "maximum_items",
        "discovery_interval_minutes",
        "retention_hours",
    ):
        if (
            isinstance(value[field], bool)
            or not isinstance(value[field], int)
            or value[field] < 1
        ):
            raise ValueError(f"registry source {field} must be positive")
    strings = ("name", "expected_language", "geographic_scope", "owner")
    if any(
        not isinstance(value[field], str) or not value[field].strip()
        for field in strings
    ):
        raise ValueError("registry source text fields must be non-empty")
    return SourceDefinition(
        id=source_id,
        name=value["name"].strip(),
        adapter=adapter,
        url=_canonical_registry_url(str(value["url"])),
        enabled=value["enabled"],
        categories=tuple(categories),
        trust_tier=trust_tier,
        default_feed_eligible=value["default_feed_eligible"],
        allow_embedding=value["allow_embedding"],
        maximum_items=value["maximum_items"],
        discovery_interval_minutes=value["discovery_interval_minutes"],
        retention_hours=value["retention_hours"],
        expected_language=value["expected_language"].strip(),
        geographic_scope=value["geographic_scope"].strip(),
        owner=value["owner"].strip(),
    )


def load_registry(path: str | Path) -> SourceRegistry:
    value = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict) or set(value) != {"version", "sources"}:
        raise ValueError("source registry must contain only version and sources")
    if value["version"] != REGISTRY_VERSION or not isinstance(value["sources"], list):
        raise ValueError("source registry version or sources is invalid")
    sources = tuple(_source(item) for item in value["sources"])
    ids = [source.id for source in sources]
    urls = [source.url.casefold() for source in sources]
    if len(ids) != len(set(ids)):
        raise ValueError("source registry IDs must be unique")
    if len(urls) != len(set(urls)):
        raise ValueError("source registry URLs must be unique")
    return SourceRegistry(REGISTRY_VERSION, sources)
