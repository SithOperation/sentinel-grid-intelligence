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

import datetime
import time


# Collectors

from collectors.news_collector import collect_news
from collectors.conflict_collector import collect_conflicts
from collectors.aircraft_collector import collect_aircraft
from collectors.maritime_collector import collect_maritime
from collectors.satellite_collector import collect_satellite
from collectors.cyber_collector import collect_cyber
from collectors.humanitarian_collector import collect_humanitarian


# Processing

from processors.data_normalizer import normalize_events
from processors.event_classifier import classify_events
from processors.confidence_scoring import apply_confidence
from processors.geolocation import apply_geolocation
from processors.event_deduplication import remove_duplicates
from intelligence.threat_scoring import analyze_threats
from intelligence.conflict_analysis import analyze_conflicts
from intelligence.regional_analysis import analyze_regions
from intelligence.intelligence_brief import generate_brief
from output.dashboard_exporter import build_dashboard
from intelligence.timeline_analysis import generate_timeline
from intelligence.trend_analysis import analyze_trends
from intelligence.map_generator import generate_map_events
from storage.event_database import append_events, apply_retention, save_events
from settings import load_config, resolve_project_path, source_enabled
from api.news import fetch as fetch_news_articles
from output.contracts import SCHEMA_VERSION
from output.publisher import publish_artifacts


# Output location

CONFIG = load_config()
OUTPUT_DIRECTORY = resolve_project_path(CONFIG["output"]["directory"])
LAST_COLLECTION_HEALTH = []


def _health_record(name, started, count, status=None, detail=None):
    return {
        "source": name,
        "status": status or ("ok" if count else "no_data"),
        "event_count": count,
        "duration_ms": round((time.monotonic() - started) * 1000),
        "detail": detail,
    }

def collect_all_sources():

    """
    Runs every intelligence collector.
    """

    events = []

    health = []
    news_enabled = source_enabled(CONFIG, "news")
    conflict_enabled = source_enabled(CONFIG, "conflict")
    started = time.monotonic()
    articles = fetch_news_articles() if news_enabled or conflict_enabled else []
    if news_enabled or conflict_enabled:
        health.append(_health_record("news_feeds", started, len(articles)))


    if source_enabled(CONFIG, "news"):
        print("[+] Collecting news intelligence")
        collected = collect_news(articles)
        events.extend(collected)
        health.append(_health_record("news", time.monotonic(), len(collected)))


    if source_enabled(CONFIG, "conflict"):
        print("[+] Collecting conflict intelligence")
        collected = collect_conflicts(articles)
        events.extend(collected)
        health.append(_health_record("conflict", time.monotonic(), len(collected)))


    if source_enabled(CONFIG, "aircraft", "opensky"):
        print("[+] Collecting aircraft intelligence")
        started = time.monotonic()
        collected = collect_aircraft()
        events.extend(collected)
        health.append(_health_record("opensky", started, len(collected)))


    if source_enabled(CONFIG, "maritime", "aisstream"):
        print("[+] Collecting maritime intelligence")
        started = time.monotonic()
        collected = collect_maritime()
        events.extend(collected)
        health.append(_health_record("aisstream", started, len(collected)))


    if source_enabled(CONFIG, "satellite", "nasa_eonet"):
        print("[+] Collecting satellite intelligence")
        started = time.monotonic()
        collected = collect_satellite()
        events.extend(collected)
        health.append(_health_record("nasa_eonet", started, len(collected)))


    if source_enabled(CONFIG, "cyber"):
        print("[+] Collecting cyber intelligence")
        started = time.monotonic()
        collected = collect_cyber()
        events.extend(collected)
        health.append(_health_record("cisa", started, len(collected)))


    if source_enabled(CONFIG, "humanitarian", "gdacs"):
        print("[+] Collecting humanitarian intelligence")
        started = time.monotonic()
        collected = collect_humanitarian()
        events.extend(collected)
        health.append(_health_record("gdacs", started, len(collected)))

    global LAST_COLLECTION_HEALTH
    LAST_COLLECTION_HEALTH = health
    return events



def process_events(events):

    """
    Intelligence processing pipeline.
    """


    events = normalize_events(
        events
    )


    events = apply_geolocation(
        events
    )


    events = classify_events(
        events
    )


    return events



def main():


    print(
        """
============================

 SENTINEL GRID INTELLIGENCE

 OSINT/GEOINT ENGINE

============================
        """
    )
    
    raw_events = collect_all_sources()

    processed_events = process_events(
        raw_events
    )


    processed_events = remove_duplicates(
        processed_events
    )

    all_events = append_events(
        processed_events
    )

    # Historical merging can change source counts. These scorers are
    # idempotent, so the complete database can safely be refreshed each run.
    all_events = apply_confidence(all_events)
    all_events = analyze_threats(all_events)
    retention = CONFIG["retention"]
    all_events = apply_retention(
        all_events,
        max_age_days=retention["max_age_days"],
        max_events=retention["max_events"],
    )
    save_events(all_events)


    conflict_analysis = analyze_conflicts(
        all_events
    )


    regional_analysis = analyze_regions(
        all_events
    )


    timeline = generate_timeline(
        all_events
    )


    trends = analyze_trends(
        all_events
    )


    map_events = generate_map_events(
        all_events
    )[-CONFIG["output"]["max_map_events"]:]

    intelligence_brief = generate_brief(
        all_events,
        regional_analysis
    )


    dashboard = build_dashboard(
        all_events,
        intelligence_brief,
        regional_analysis
    )

    generated = datetime.datetime.now(datetime.UTC).isoformat()
    world_events = {
        "schema_version": SCHEMA_VERSION,
        "generated": generated,
        "total_events": len(all_events),
        "events": all_events,
    }
    health = {
        "schema_version": SCHEMA_VERSION,
        "generated": generated,
        "status": "healthy" if all(item["status"] == "ok" for item in LAST_COLLECTION_HEALTH) else "degraded",
        "sources": LAST_COLLECTION_HEALTH,
        "published_event_count": len(all_events),
        "freshness": {
            "oldest_event": min((event.get("timestamp", "") for event in all_events), default=None),
            "newest_event": max((event.get("timestamp", "") for event in all_events), default=None),
        },
    }
    artifacts = {
        "world_events.json": world_events,
        "intelligence_brief.json": intelligence_brief,
        "timeline.json": timeline,
        "trends.json": trends,
        "map_events.json": map_events,
        "dashboard.json": dashboard,
        "health.json": health,
    }
    manifest = publish_artifacts(
        artifacts,
        OUTPUT_DIRECTORY,
        max_file_size_mb=CONFIG["output"]["max_file_size_mb"],
    )

    print(
        f"[+] Intelligence update complete ({manifest['publication_id']})"
    )



if __name__ == "__main__":

    main()
