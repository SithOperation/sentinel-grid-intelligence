from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from sources.models import DiscoveredItem
from sources.registry import load_registry

ROOT = Path(__file__).resolve().parents[1]


def test_authoritative_registry_contains_controlled_sources():
    registry = load_registry(ROOT / "config/source_registry.yaml")
    assert registry.version == "1.0"
    assert len(registry.sources) == 18
    assert {source.adapter for source in registry.sources} == {"x", "reddit", "website"}
    assert len({source.id for source in registry.sources}) == 18


def test_registry_rejects_unknown_fields(tmp_path):
    value = yaml.safe_load((ROOT / "config/source_registry.yaml").read_text())
    value["sources"][0]["surprise"] = True
    path = tmp_path / "registry.yaml"
    path.write_text(yaml.safe_dump(value), encoding="utf-8")
    with pytest.raises(ValueError, match="unknown fields"):
        load_registry(path)


def test_registry_rejects_duplicate_canonical_urls(tmp_path):
    value = yaml.safe_load((ROOT / "config/source_registry.yaml").read_text())
    value["sources"][1]["url"] = "https://twitter.com/Worldsource24/"
    path = tmp_path / "registry.yaml"
    path.write_text(yaml.safe_dump(value), encoding="utf-8")
    with pytest.raises(ValueError, match="URLs must be unique"):
        load_registry(path)


def test_stable_id_does_not_depend_on_mutable_text():
    now = datetime(2026, 7, 28, tzinfo=UTC)
    common = {
        "source_id": "example",
        "platform": "x",
        "canonical_url": "https://x.com/example/status/123",
        "platform_item_id": "123",
        "published_at": now,
        "discovered_at": now,
        "title": None,
    }
    first = DiscoveredItem(**common, text="original")
    edited = DiscoveredItem(**common, text="edited")
    assert first.stable_id == edited.stable_id
