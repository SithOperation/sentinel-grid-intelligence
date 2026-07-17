"""Validated staging and atomic-per-file publication for static JSON data."""

from datetime import datetime, timezone
from pathlib import Path
import json
import os
import tempfile
import uuid

from output.contracts import SCHEMA_VERSION, validate_artifacts


def _encoded(data):
    return json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")


def publish_artifacts(artifacts, output_directory, max_file_size_mb=25):
    validate_artifacts(artifacts)
    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    publication_id = uuid.uuid4().hex
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
        "generated": datetime.now(timezone.utc).isoformat(),
        "files": {name: len(payload) for name, payload in encoded.items()},
    }

    with tempfile.TemporaryDirectory(prefix="sentinel-stage-", dir=output_directory.parent) as stage:
        stage_path = Path(stage)
        for filename, payload in encoded.items():
            (stage_path / filename).write_bytes(payload)
        (stage_path / "manifest.json").write_bytes(_encoded(manifest))

        # The manifest is replaced last; consumers can use its publication ID
        # as the signal that a complete validated release is available.
        for filename in encoded:
            os.replace(stage_path / filename, output_directory / filename)
        os.replace(stage_path / "manifest.json", output_directory / "manifest.json")

    return manifest
