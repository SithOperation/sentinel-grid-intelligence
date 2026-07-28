import json
from pathlib import Path

import yaml


def test_collection_dispatches_validated_publication_metadata() -> None:
    workflow_path = Path(__file__).parents[1] / ".github" / "workflows" / "collect.yml"
    workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    collect = workflow["jobs"]["collect"]
    text = json.dumps(collect)

    assert "sentinel-publication-updated" in text
    assert "WEBSITE_DISPATCH_TOKEN" in text
    assert "publication_id" in text
    assert "source_commit" in text
    assert "generated" in text
    assert "map_event_count" in text
    assert "scheduled website synchronization remains active" in text
