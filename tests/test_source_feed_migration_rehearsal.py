import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import main as pipeline
from storage import event_database

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = datetime(2026, 7, 28, 12, tzinfo=UTC)


def generate_offline_release(root, events):
    root.mkdir(parents=True)
    database = root / "events.json"
    database.write_text(json.dumps(events), encoding="utf-8")
    output = root / "output"
    with (
        patch.object(pipeline, "OUTPUT_DIRECTORY", output),
        patch.object(event_database, "DATABASE_PATH", database),
    ):
        pipeline.main(use_existing=True, reference_time=REFERENCE)
        pipeline.validate_existing_publication()
    return output


def json_shape(value):
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def verify_manifest(directory):
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    for name, metadata in manifest["files"].items():
        payload = (directory / name).read_bytes()
        assert len(payload) == metadata["bytes"]
        assert hashlib.sha256(payload).hexdigest() == metadata["sha256"]
    source_feed = json.loads(
        (directory / "source_feed.json").read_text(encoding="utf-8")
    )
    assert source_feed["publication_id"] == manifest["publication_id"]
    return manifest


def test_offline_migration_rehearsal_preserves_shapes_and_syncs_one_release(tmp_path):
    events = event_database.load_events()
    first = generate_offline_release(tmp_path / "first", events)
    second = generate_offline_release(tmp_path / "second", events)
    first_manifest = verify_manifest(first)
    second_manifest = verify_manifest(second)

    baseline_files = {
        path.name for path in (ROOT / "data/output").iterdir() if path.is_file()
    }
    assert {path.name for path in first.iterdir()} == baseline_files | {
        "source_feed.json"
    }

    for name in baseline_files - {"manifest.json"}:
        baseline = json.loads((ROOT / "data/output" / name).read_text(encoding="utf-8"))
        migrated = json.loads((first / name).read_text(encoding="utf-8"))
        assert json_shape(migrated) == json_shape(baseline)

    assert (
        json_shape(json.loads((first / "map_events.json").read_text(encoding="utf-8")))
        == "array"
    )
    assert (
        json_shape(json.loads((first / "timeline.json").read_text(encoding="utf-8")))
        == "array"
    )

    deterministic_files = baseline_files - {"manifest.json", "health.json"}
    for name in deterministic_files:
        assert (first / name).read_bytes() == (second / name).read_bytes()

    first_health = json.loads((first / "health.json").read_text(encoding="utf-8"))
    second_health = json.loads((second / "health.json").read_text(encoding="utf-8"))
    first_sources = first_health.pop("sources")
    second_sources = second_health.pop("sources")
    assert first_health == second_health
    assert [
        {
            key: value
            for key, value in source.items()
            if key not in {"checked_at", "last_success"}
        }
        for source in first_sources
    ] == [
        {
            key: value
            for key, value in source.items()
            if key not in {"checked_at", "last_success"}
        }
        for source in second_sources
    ]
    assert first_health["source_feed"]["status"] == "unavailable"

    assert first_manifest["publication_id"] != second_manifest["publication_id"]
    assert "source_feed.json" in first_manifest["files"]

    synchronized = tmp_path / "dry-run-website-data"
    shutil.copytree(first, synchronized)
    synchronized_manifest = verify_manifest(synchronized)
    assert synchronized_manifest["publication_id"] == first_manifest["publication_id"]
