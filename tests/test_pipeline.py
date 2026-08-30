import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import main as pipeline
from intelligence.map_generator import generate_map_events
from intelligence.threat_scoring import analyze_threats
from models.event_model import create_event
from output.contracts import SCHEMA_VERSION, ContractError
from output.health import build_health
from output.publisher import publish_artifacts
from processors.confidence_scoring import apply_confidence
from processors.data_normalizer import normalize_events
from processors.event_classifier import classify_events
from processors.event_deduplication import remove_duplicates
from processors.geolocation import apply_geolocation
from settings import load_config, source_enabled
from storage import event_database
from storage.event_database import apply_retention
from utils.sanitization import plain_text, safe_url


class SettingsTests(unittest.TestCase):
    def test_repository_config_matches_runtime_sources(self):
        config = load_config()
        self.assertTrue(source_enabled(config, "eonet"))
        self.assertTrue(source_enabled(config, "humanitarian", "gdacs"))
        self.assertTrue(source_enabled(config, "earthquake", "usgs"))
        self.assertTrue(config["sources"]["eonet"]["collect_volcanoes"])
        self.assertTrue(source_enabled(config, "weather", "nws"))
        self.assertEqual(config["retention"]["max_age_hours"], 72)

    def test_invalid_limits_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.yaml"
            path.write_text("output:\n  max_map_events: 0\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_config(path)


class PipelineTests(unittest.TestCase):
    def test_pipeline_geolocates_scores_and_maps_event(self):
        event = create_event(
            "conflict",
            "conflict_report",
            "Missile attack reported near Kyiv",
            source=["Reuters"],
            priority="high",
            confidence=70,
        )

        events = normalize_events([event])
        events = apply_geolocation(events)
        events = classify_events(events)
        events = remove_duplicates(events)
        events = apply_confidence(events)
        events = analyze_threats(events)
        mapped = generate_map_events(events)

        self.assertEqual(events[0]["category"], "conflict")
        self.assertEqual(events[0]["location"]["city"], "Kyiv")
        self.assertEqual(events[0]["confidence"], 85)
        self.assertEqual(events[0]["threat_level"], "CRITICAL")
        self.assertEqual(len(mapped), 1)

    def test_deduplication_uses_unique_sources_for_verification(self):
        first = create_event("news", "report", "Same title", source=["BBC"])
        second = create_event("news", "report", "Same title", source=["BBC"])
        third = create_event("news", "report", "Same title", source=["Reuters"])

        result = remove_duplicates([first, second, third])

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["duplicate_count"], 3)
        self.assertEqual(result[0]["source"], ["BBC", "Reuters"])
        self.assertEqual(result[0]["verification"]["source_count"], 2)

    def test_confidence_scoring_is_idempotent(self):
        event = create_event(
            "conflict", "report", "Verified report", source=["Reuters"], confidence=70
        )
        apply_confidence([event])
        first_score = event["confidence"]
        apply_confidence([event])
        self.assertEqual(event["confidence"], first_score)

    def test_stable_event_id_is_derived_from_fingerprint(self):
        first = create_event("news", "report", "Stable title", source=["BBC"])
        second = create_event("news", "report", "Stable title", source=["Reuters"])
        first_id = remove_duplicates([first])[0]["event_id"]
        second_id = remove_duplicates([second])[0]["event_id"]
        self.assertEqual(first_id, second_id)

    def test_map_rejects_invalid_coordinates_but_keeps_equator(self):
        events = [
            {
                "event_id": "unknown",
                "event_type": "earthquake",
                "location": {"latitude": 0, "longitude": 0},
            },
            {
                "event_id": "bad",
                "event_type": "earthquake",
                "location": {"latitude": 100, "longitude": 20},
            },
            {
                "event_id": "equator",
                "event_type": "earthquake",
                "location": {"latitude": 0, "longitude": 20},
            },
        ]
        self.assertEqual(
            [event["event_id"] for event in generate_map_events(events)],
            ["equator"],
        )

    def test_database_merges_across_runs(self):
        event = create_event("conflict", "report", "Verified event", source=["Reuters"])
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "events.json"
            with patch.object(event_database, "DATABASE_PATH", database_path):
                event_database.append_events([event])
                merged = event_database.append_events([event.copy()])

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["duplicate_count"], 2)

    def test_main_writes_all_frontend_outputs_without_live_apis(self):
        event = create_event(
            "conflict",
            "conflict_report",
            "Missile activity in Ukraine",
            source=["Reuters"],
            priority="high",
            confidence=70,
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with (
                patch.object(pipeline, "collect_all_sources", return_value=[event]),
                patch.object(event_database, "DATABASE_PATH", root / "events.json"),
                patch.object(pipeline, "OUTPUT_DIRECTORY", root),
                patch("output.publisher.os.replace", wraps=os.replace) as replace,
            ):
                pipeline.main()

            expected = [
                root / "world_events.json",
                root / "intelligence_brief.json",
                root / "timeline.json",
                root / "trends.json",
                root / "map_events.json",
                root / "dashboard.json",
                root / "health.json",
                root / "manifest.json",
                root / "events.json",
            ]
            self.assertTrue(all(path.exists() for path in expected))
            world = json.loads((root / "world_events.json").read_text(encoding="utf-8"))
            self.assertEqual(world["schema_version"], SCHEMA_VERSION)
            manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(
                Path(replace.call_args_list[-1].args[1]).name, "manifest.json"
            )
            self.assertEqual(len(manifest["files"]["map_events.json"]["sha256"]), 64)

    def test_offline_publication_does_not_call_collectors(self):
        event = create_event("news", "report", "Stored event", source=["BBC"])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with (
                patch.object(event_database, "DATABASE_PATH", root / "events.json"),
                patch.object(pipeline, "OUTPUT_DIRECTORY", root),
                patch.object(
                    pipeline,
                    "collect_all_sources",
                    side_effect=AssertionError("network path called"),
                ),
            ):
                event_database.save_events([event])
                pipeline.main(use_existing=True)
            health = json.loads((root / "health.json").read_text(encoding="utf-8"))
            self.assertEqual(health["status"], "degraded")
            self.assertTrue(
                all(
                    item["status"] in {"not_checked", "disabled"}
                    for item in health["sources"]
                )
            )

    def test_invalid_release_does_not_replace_current_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            current = root / "world_events.json"
            current.write_text("current", encoding="utf-8")
            with self.assertRaises(ContractError):
                publish_artifacts({"world_events.json": {}}, root)
            self.assertEqual(current.read_text(encoding="utf-8"), "current")

    def test_retention_limits_age_and_count(self):
        now = datetime.now(timezone.utc)
        events = []
        for hours in (72, 3, 2, 1):
            events.append(
                {
                    "timestamp": (now - timedelta(hours=hours)).isoformat(),
                    "hours": hours,
                }
            )
        retained = apply_retention(events, max_age_hours=72, max_events=2, now=now)
        self.assertEqual([event["hours"] for event in retained], [2, 1])

    def test_feed_content_is_sanitized(self):
        self.assertEqual(
            plain_text("<b>Hello</b><script>bad()</script>", 100), "Hello bad()"
        )
        self.assertEqual(safe_url("javascript:alert(1)"), "")
        self.assertEqual(
            safe_url("https://example.com/report"), "https://example.com/report"
        )

    def test_health_marks_old_data_stale(self):
        generated = datetime.now(timezone.utc)
        old = generated - timedelta(hours=8)
        health = build_health(
            [{"timestamp": old.isoformat()}],
            [{"source": "test", "status": "ok"}],
            generated.isoformat(),
            stale_after_minutes=390,
        )
        self.assertTrue(health["stale"])
        self.assertTrue(health["degraded"])

    def test_health_does_not_treat_zero_current_events_as_an_outage(self):
        generated = datetime.now(timezone.utc)
        health = build_health(
            [{"timestamp": generated.isoformat()}],
            [{"source": "inactive-volcano-feed", "status": "no_data"}],
            generated.isoformat(),
            stale_after_minutes=390,
        )
        self.assertFalse(health["stale"])
        self.assertFalse(health["degraded"])
        self.assertEqual(health["status"], "healthy")


if __name__ == "__main__":
    unittest.main()
