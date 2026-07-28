import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

import pytest

from output.contracts import ContractError, validate_artifacts
from output.publisher import publish_artifacts
from sources.feed import build_source_feed, validate_source_feed
from sources.models import DiscoveredItem

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 7, 28, 12, tzinfo=UTC)
FILES = {
    "world_events.json",
    "intelligence_brief.json",
    "timeline.json",
    "trends.json",
    "map_events.json",
    "dashboard.json",
    "health.json",
    "x_reports.json",
    "x_report_events.json",
    "x_report_pinpoints.geojson",
}


def baseline_artifacts(publication_id):
    artifacts = {
        name: json.loads((ROOT / "data/output" / name).read_text(encoding="utf-8"))
        for name in FILES
    }
    generated = datetime.fromisoformat(artifacts["world_events.json"]["generated"])
    artifacts["source_feed.json"] = build_source_feed(
        [], [], publication_id=publication_id, generated_at=generated
    )
    artifacts["health.json"]["source_feed"] = artifacts["source_feed.json"]["health"]
    return artifacts, generated


def test_empty_source_feed_is_mandatory_and_valid():
    publication_id = "a" * 32
    artifacts, _ = baseline_artifacts(publication_id)
    assert validate_artifacts(artifacts)
    assert artifacts["source_feed.json"]["count"] == 0
    assert artifacts["source_feed.json"]["health"]["status"] == "unavailable"


def test_manifest_hashes_source_feed_and_uses_one_publication_id(tmp_path):
    publication_id = "b" * 32
    artifacts, generated = baseline_artifacts(publication_id)
    manifest = publish_artifacts(
        artifacts,
        tmp_path,
        publication_id=publication_id,
        generated=generated,
    )
    source_feed = json.loads((tmp_path / "source_feed.json").read_text())
    assert manifest["publication_id"] == source_feed["publication_id"]
    assert manifest["files"]["source_feed.json"]["bytes"] > 0
    assert len(manifest["files"]["source_feed.json"]["sha256"]) == 64


def test_mixed_source_feed_publication_is_rejected(tmp_path):
    artifacts, generated = baseline_artifacts("c" * 32)
    with pytest.raises(ValueError, match="release publication ID"):
        publish_artifacts(
            artifacts,
            tmp_path,
            publication_id="d" * 32,
            generated=generated,
        )


def test_mid_release_failure_restores_exact_previous_files(tmp_path):
    old_id = "e" * 32
    old_artifacts, generated = baseline_artifacts(old_id)
    publish_artifacts(
        old_artifacts, tmp_path, publication_id=old_id, generated=generated
    )
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir()}

    new_id = "f" * 32
    new_artifacts, _ = baseline_artifacts(new_id)
    real_replace = os.replace
    replacement_count = 0

    def fail_once(source, destination):
        nonlocal replacement_count
        replacement_count += 1
        if replacement_count == 3:
            raise OSError("simulated publication failure")
        return real_replace(source, destination)

    with (
        patch("output.publisher.os.replace", side_effect=fail_once),
        pytest.raises(OSError, match="simulated"),
    ):
        publish_artifacts(
            new_artifacts,
            tmp_path,
            publication_id=new_id,
            generated=generated,
        )
    after = {path.name: path.read_bytes() for path in tmp_path.iterdir()}
    assert after == before


def test_source_feed_contract_failure_rejects_complete_release(tmp_path):
    artifacts, generated = baseline_artifacts("1" * 32)
    artifacts["source_feed.json"]["count"] = 1
    with pytest.raises(ContractError, match="source_feed"):
        publish_artifacts(
            artifacts,
            tmp_path,
            publication_id="1" * 32,
            generated=generated,
        )


def test_item_contract_separates_confidences_and_hashes_sanitized_content():
    item = DiscoveredItem(
        source_id="example",
        platform="x",
        canonical_url="https://x.com/example/status/123",
        platform_item_id="123",
        published_at=NOW,
        discovered_at=NOW,
        title="Report",
        text="<b>Source report</b>",
    )
    feed = build_source_feed([item], [], publication_id="2" * 32, generated_at=NOW)
    public = cast(list[dict[str, Any]], feed["items"])[0]
    assert public["location_confidence"] == 0.0
    assert public["claim_confidence"] == 0.0
    assert public["association_confidence"] == 0.0
    assert public["content_hash"].startswith("sha256:")
    assert len(public["content_hash"]) == 71


def test_invalid_confidence_cannot_be_published():
    item = DiscoveredItem(
        source_id="example",
        platform="x",
        canonical_url="https://x.com/example/status/123",
        platform_item_id="123",
        published_at=NOW,
        discovered_at=NOW,
        title=None,
        text="Report",
    )
    feed = build_source_feed([item], [], publication_id="3" * 32, generated_at=NOW)
    cast(list[dict[str, Any]], feed["items"])[0]["claim_confidence"] = 1.1
    with pytest.raises(ValueError, match="claim_confidence"):
        validate_source_feed(feed, reference_time=NOW)


def test_schema_file_is_valid_json_and_disallows_extra_item_fields():
    schema = json.loads((ROOT / "schema/source_feed.schema.json").read_text())
    assert schema["properties"]["items"]["items"]["additionalProperties"] is False
