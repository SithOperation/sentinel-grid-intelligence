"""
Sentinel Grid Intelligence Engine

Main processing pipeline.

Flow:

Collectors
    |
    v
Raw Events
    |
    v
Processors
    |
    v
Normalized Intelligence
    |
    v
JSON Output

"""

import argparse
import datetime
import json
import time

from api.bounded_json import ProviderError
from api.nasa_eonet import fetch as fetch_eonet
from api.news import fetch as fetch_news_articles
from api.x_public import PublicXTransport
from collectors.conflict_collector import collect_conflicts
from collectors.earthquake_collector import collect_earthquakes
from collectors.hazard_common import CollectionResult
from collectors.humanitarian_collector import collect_humanitarian

# Collectors
from collectors.satellite_collector import collect_natural_events
from collectors.volcano_collector import collect_volcanoes
from collectors.weather_collector import collect_weather_alerts
from collectors.x_collector import XCollector, load_x_urls
from intelligence.intelligence_brief import generate_brief
from intelligence.map_generator import generate_map_events
from intelligence.regional_analysis import analyze_regions
from intelligence.threat_scoring import analyze_threats
from intelligence.timeline_analysis import generate_timeline
from intelligence.trend_analysis import analyze_trends
from models.x_report import build_x_report_document, build_x_website_artifacts
from output.contracts import SCHEMA_VERSION, validate_artifacts
from output.dashboard_exporter import build_dashboard
from output.health import build_health
from output.publisher import publish_artifacts
from processors.confidence_scoring import apply_confidence

# Processing
from processors.data_normalizer import normalize_events
from processors.event_classifier import classify_events
from processors.event_deduplication import remove_duplicates
from processors.geolocation import apply_geolocation
from settings import (
    load_config,
    resolve_project_path,
    source_enabled,
)
from storage import event_database
from storage.event_database import (
    append_events,
    apply_retention,
    load_events,
    save_events,
)

# Output location

CONFIG = load_config()
OUTPUT_DIRECTORY = resolve_project_path(CONFIG["output"]["directory"])
LAST_COLLECTION_HEALTH = []
SUPPORTED_EVENT_TYPES = {
    "conflict",
    "humanitarian",
    "earthquake",
    "volcano",
    "weather_alert",
    "wildfire",
    "flood",
    "tropical_cyclone",
    "natural_hazard",
    "x_report",
}


def _health_record(name, started, count, status=None, detail=None):
    checked_at = datetime.datetime.now(datetime.UTC).isoformat()
    final_status = status or ("ok" if count else "no_data")
    return {
        "source": name,
        "enabled": final_status != "disabled",
        "status": final_status,
        "event_count": count,
        "duration_ms": round((time.monotonic() - started) * 1000),
        "checked_at": checked_at,
        "last_success": checked_at if final_status == "ok" else None,
        "error": detail,
    }


def _result_health(name, started, result):
    record = _health_record(
        name, started, len(result.events), status=result.status, detail=result.error
    )
    record["metrics"] = result.metrics
    return record


def _configured_sources():
    return {
        "conflict": source_enabled(CONFIG, "conflict"),
        "nasa_eonet_natural_events": source_enabled(CONFIG, "eonet")
        and CONFIG["sources"]["eonet"]["collect_natural_events"],
        "usgs_earthquakes": source_enabled(CONFIG, "earthquake", "usgs"),
        "nasa_eonet_volcanoes": source_enabled(CONFIG, "eonet")
        and CONFIG["sources"]["eonet"]["collect_volcanoes"],
        "nws_weather_alerts": source_enabled(CONFIG, "weather", "nws"),
        "gdacs": source_enabled(CONFIG, "humanitarian", "gdacs"),
        "x": source_enabled(CONFIG, "x"),
    }


def _offline_health():
    records = []
    for name, enabled in _configured_sources().items():
        record = _health_record(
            name,
            time.monotonic(),
            0,
            status="not_checked" if enabled else "disabled",
        )
        record["note"] = (
            "Offline publication reused the retained database" if enabled else None
        )
        records.append(record)
    return records


def collect_all_sources(reference_time=None):
    """
    Runs every intelligence collector.
    """

    reference_time = reference_time or datetime.datetime.now(datetime.UTC)
    events = []

    health = []
    conflict_enabled = source_enabled(CONFIG, "conflict")
    started = time.monotonic()
    articles = fetch_news_articles() if conflict_enabled else []

    if source_enabled(CONFIG, "conflict"):
        print("[+] Collecting conflict intelligence")
        started = time.monotonic()
        collected = collect_conflicts(articles)
        events.extend(collected)
        health.append(_health_record("conflict", started, len(collected)))

    if source_enabled(CONFIG, "eonet"):
        eonet_config = CONFIG["sources"]["eonet"]
        print("[+] Collecting NASA EONET natural-hazard intelligence")
        started = time.monotonic()
        try:
            separator = "&" if "?" in eonet_config["endpoint_url"] else "?"
            eonet_url = (
                f"{eonet_config['endpoint_url']}{separator}status=open&limit=200"
            )
            eonet_response = fetch_eonet(
                eonet_url,
                connection_timeout_seconds=eonet_config["connection_timeout_seconds"],
                request_timeout_seconds=eonet_config["request_timeout_seconds"],
                max_response_bytes=eonet_config["max_response_bytes"],
            )
            eonet_error = None
        except ProviderError as error:
            eonet_response = None
            eonet_error = str(error)
        for enabled, name, collector in (
            (
                eonet_config["collect_natural_events"],
                "nasa_eonet_natural_events",
                collect_natural_events,
            ),
            (
                eonet_config["collect_volcanoes"],
                "nasa_eonet_volcanoes",
                collect_volcanoes,
            ),
        ):
            if not enabled:
                continue
            result = (
                CollectionResult(status="error", error=eonet_error)
                if eonet_response is None
                else collector(eonet_config, reference_time, response=eonet_response)
            )
            events.extend(result.events)
            health.append(_result_health(name, started, result))

    if source_enabled(CONFIG, "earthquake", "usgs"):
        print("[+] Collecting USGS earthquake intelligence")
        started = time.monotonic()
        result = collect_earthquakes(
            CONFIG["sources"]["earthquake"]["usgs"], reference_time
        )
        events.extend(result.events)
        health.append(_result_health("usgs_earthquakes", started, result))

    if source_enabled(CONFIG, "weather", "nws"):
        print("[+] Collecting NWS weather-alert intelligence")
        started = time.monotonic()
        result = collect_weather_alerts(
            CONFIG["sources"]["weather"]["nws"], reference_time
        )
        events.extend(result.events)
        health.append(_result_health("nws_weather_alerts", started, result))

    if source_enabled(CONFIG, "humanitarian", "gdacs"):
        print("[+] Collecting humanitarian intelligence")
        started = time.monotonic()
        collected = collect_humanitarian()
        events.extend(collected)
        health.append(_health_record("gdacs", started, len(collected)))

    if source_enabled(CONFIG, "x"):
        print("[+] Collecting X early-report intelligence")
        started = time.monotonic()
        x_config = CONFIG["sources"]["x"]
        try:
            url_values = x_config["urls"]
            if not isinstance(url_values, list):
                raise TypeError("X configuration requires a urls array")
            urls = load_x_urls(url_values)
            collector = XCollector(
                urls,
                reference_time=reference_time,
                transport=PublicXTransport(
                    connect_timeout_seconds=x_config["connection_timeout_seconds"],
                    read_timeout_seconds=x_config["request_timeout_seconds"],
                    max_response_bytes=x_config["max_response_bytes"],
                ),
                cache_path=resolve_project_path(x_config["cache_file"]),
                request_interval_seconds=x_config["request_interval_seconds"],
                max_urls_per_run=x_config["max_urls_per_run"],
            )
            result = collector.collect()
            collected = list(result.events)
            events.extend(collected)
            failures = [
                item
                for item in result.urls
                if item.status in {"rejected", "unavailable"}
            ]
            detail = "; ".join(f"{item.url}: {item.reason}" for item in failures)
            record = _health_record(
                "x",
                started,
                len(collected),
                status=(
                    "error"
                    if result.total_failure
                    else "partial"
                    if result.partial
                    else None
                ),
                detail=detail or None,
            )
            record["metrics"] = result.health_metrics()
            health.append(record)
        except (OSError, TypeError, ValueError) as error:
            print(f"[!] X collector failed safely: {error}")
            health.append(
                _health_record("x", started, 0, status="error", detail=str(error))
            )

    present = {item["source"] for item in health}
    for name, enabled in _configured_sources().items():
        if not enabled and name not in present:
            health.append(_health_record(name, time.monotonic(), 0, status="disabled"))

    global LAST_COLLECTION_HEALTH
    LAST_COLLECTION_HEALTH = health
    return events


def process_events(events):
    """
    Intelligence processing pipeline.
    """

    events = [
        event for event in events if event.get("event_type") in SUPPORTED_EVENT_TYPES
    ]
    events = normalize_events(events)

    events = apply_geolocation(events)

    events = classify_events(events)

    return events


def main(use_existing=False, reference_time=None):

    print(
        """
============================

 SENTINEL GRID INTELLIGENCE

 OSINT/GEOINT ENGINE

============================
        """
    )

    reference_time = reference_time or datetime.datetime.now(datetime.UTC)
    global LAST_COLLECTION_HEALTH
    if use_existing:
        raw_events = load_events()
        LAST_COLLECTION_HEALTH = _offline_health()
    else:
        raw_events = collect_all_sources(reference_time)

    processed_events = process_events(raw_events)

    processed_events = remove_duplicates(processed_events)

    all_events = processed_events if use_existing else append_events(processed_events)

    # Historical merging can change source counts. These scorers are
    # idempotent, so the complete database can safely be refreshed each run.
    all_events = apply_confidence(all_events)
    all_events = analyze_threats(all_events)
    retention = CONFIG["retention"]
    all_events = apply_retention(
        all_events,
        max_age_hours=retention["max_age_hours"],
        max_events=retention["max_events"],
        now=reference_time,
    )
    save_events(all_events)

    regional_analysis = analyze_regions(all_events)

    timeline = generate_timeline(all_events)

    trends = analyze_trends(all_events)

    map_events = generate_map_events(all_events)[-CONFIG["output"]["max_map_events"] :]

    intelligence_brief = generate_brief(all_events, regional_analysis)

    dashboard = build_dashboard(
        all_events,
        intelligence_brief,
        regional_analysis,
        generated=reference_time,
    )

    generated = reference_time.isoformat()
    world_events = {
        "schema_version": SCHEMA_VERSION,
        "generated": generated,
        "total_events": len(all_events),
        "events": all_events,
    }
    health = build_health(
        all_events,
        LAST_COLLECTION_HEALTH,
        generated,
        CONFIG["output"]["stale_after_minutes"],
    )
    x_reports = build_x_report_document(all_events, reference_time)
    x_report_events, x_report_pinpoints = build_x_website_artifacts(
        x_reports,
        reference_time,
    )
    artifacts = {
        "world_events.json": world_events,
        "intelligence_brief.json": intelligence_brief,
        "timeline.json": timeline,
        "trends.json": trends,
        "map_events.json": map_events,
        "dashboard.json": dashboard,
        "health.json": health,
        "x_reports.json": x_reports,
        "x_report_events.json": x_report_events,
        "x_report_pinpoints.geojson": x_report_pinpoints,
    }
    manifest = publish_artifacts(
        artifacts,
        OUTPUT_DIRECTORY,
        max_file_size_mb=CONFIG["output"]["max_file_size_mb"],
        generated=reference_time,
    )

    print(f"[+] Intelligence update complete ({manifest['publication_id']})")


RUNTIME_OUTPUT_FILES = {
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
    "manifest.json",
}


def reset_generated_data():
    """Remove only Sentinel's explicitly known generated and retained files."""
    targets = [OUTPUT_DIRECTORY / name for name in RUNTIME_OUTPUT_FILES]
    targets.append(event_database.DATABASE_PATH)
    x_cache = resolve_project_path(CONFIG["sources"]["x"]["cache_file"])
    targets.append(x_cache)
    removed = []
    for path in targets:
        if path.is_file():
            path.unlink()
            removed.append(path)
    return removed


def validate_existing_publication():
    artifacts = {}
    for name in RUNTIME_OUTPUT_FILES - {"manifest.json"}:
        path = OUTPUT_DIRECTORY / name
        artifacts[name] = json.loads(path.read_text(encoding="utf-8"))
    validate_artifacts(artifacts)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sentinel Grid intelligence publisher")
    parser.add_argument(
        "--publish-existing",
        action="store_true",
        help="Publish the retained database without contacting external sources",
    )
    parser.add_argument(
        "--reset-generated-data",
        action="store_true",
        help="Deliberately remove only known generated outputs, retained events, and X cache",
    )
    parser.add_argument(
        "--validate-existing",
        action="store_true",
        help="Validate the currently published artifact group",
    )
    arguments = parser.parse_args()
    if arguments.reset_generated_data:
        for removed_path in reset_generated_data():
            print(f"[-] Removed runtime file: {removed_path}")
    elif arguments.validate_existing:
        validate_existing_publication()
        print("[+] Existing publication contracts are valid")
    else:
        main(use_existing=arguments.publish_existing)
