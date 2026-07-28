"""Validated staging and atomic-per-file publication for static JSON data."""

import hashlib
import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from output.contracts import SCHEMA_VERSION, validate_artifacts


def _encoded(data):
    return json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")


def publish_artifacts(
    artifacts,
    output_directory,
    max_file_size_mb=25,
    generated=None,
    publication_id=None,
):
    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    publication_id = publication_id or uuid.uuid4().hex
    validate_artifacts(artifacts)
    source_feed = artifacts.get("source_feed.json")
    if (
        not isinstance(source_feed, dict)
        or source_feed.get("publication_id") != publication_id
    ):
        raise ValueError("source_feed.json must use the release publication ID")
    size_limit = max_file_size_mb * 1024 * 1024
    encoded = {}

    for filename, data in artifacts.items():
        payload = _encoded(data)
        if len(payload) > size_limit:
            raise ValueError(f"{filename} exceeds the {max_file_size_mb} MB limit")
        encoded[filename] = payload

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "publication_id": publication_id,
        "generated": (generated or datetime.now(timezone.utc))
        .astimezone(timezone.utc)
        .isoformat(),
        "files": {
            name: {
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
            for name, payload in encoded.items()
        },
    }

    with tempfile.TemporaryDirectory(
        prefix="sentinel-stage-", dir=output_directory.parent
    ) as stage:
        stage_path = Path(stage)
        for filename, payload in encoded.items():
            (stage_path / filename).write_bytes(payload)
        (stage_path / "manifest.json").write_bytes(_encoded(manifest))

        backup_path = stage_path / "previous"
        backup_path.mkdir()
        release_files = [*encoded, "manifest.json"]
        existed = {
            filename: (output_directory / filename).is_file()
            for filename in release_files
        }
        for filename, present in existed.items():
            if present:
                (backup_path / filename).write_bytes(
                    (output_directory / filename).read_bytes()
                )
        try:
            # The manifest is replaced last; consumers can use its publication ID
            # as the signal that a complete validated release is available.
            for filename in encoded:
                os.replace(stage_path / filename, output_directory / filename)
            os.replace(stage_path / "manifest.json", output_directory / "manifest.json")
        except Exception:
            for filename in release_files:
                target = output_directory / filename
                if existed[filename]:
                    os.replace(backup_path / filename, target)
                else:
                    target.unlink(missing_ok=True)
            raise

    return manifest
