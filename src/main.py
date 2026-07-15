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

from pathlib import Path
import json
import datetime


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
from output.dashboard_exporter import export_dashboard
from intelligence.timeline_analysis import generate_timeline
from intelligence.trend_analysis import analyze_trends
from intelligence.map_generator import generate_map_events
from intelligence.dashboard_generator import generate_dashboard
from storage.event_database import append_events


# Output location

OUTPUT_PATH = Path(
    "data/output/world_events.json"
)

BRIEF_PATH = Path(
    "data/output/intelligence_brief.json"
)

TIMELINE_PATH = Path(
    "data/output/timeline.json"
)

TREND_PATH = Path(
    "data/output/trends.json"
)

MAP_PATH = Path(
    "data/output/map_events.json"
)

DASHBOARD_PATH = Path(
    "data/output/dashboard.json"
)

def collect_all_sources():

    """
    Runs every intelligence collector.
    """

    events = []


    print("[+] Collecting news intelligence")
    events.extend(
        collect_news()
    )


    print("[+] Collecting conflict intelligence")
    events.extend(
        collect_conflicts()
    )


    print("[+] Collecting aircraft intelligence")
    events.extend(
        collect_aircraft()
    )


    print("[+] Collecting maritime intelligence")
    events.extend(
        collect_maritime()
    )


    print("[+] Collecting satellite intelligence")
    events.extend(
        collect_satellite()
    )


    print("[+] Collecting cyber intelligence")
    events.extend(
        collect_cyber()
    )


    print("[+] Collecting humanitarian intelligence")
    events.extend(
        collect_humanitarian()
    )


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


    events = apply_confidence(
        events
    )


    return events



def save_output(events, brief=None):

    """
    Writes final intelligence JSON.
    """


    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )


    output = {

        "generated":

        datetime.datetime.now(datetime.UTC)
        .isoformat(),


        "total_events":

        len(events),


        "events":

        events

    }


    with open(
        OUTPUT_PATH,
        "w",
        encoding="utf-8"
    ) as file:


        json.dump(
            output,
            file,
            indent=4
        )


    print(
        f"[+] Saved {len(events)} events"
    )

    if brief:


        with open(
            BRIEF_PATH,
            "w",
            encoding="utf-8"
        ) as file:


            json.dump(
                brief,
                file,
                indent=4
            )


    print(
        "[+] Saved intelligence brief"
    )


def save_timeline(timeline):

    TIMELINE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )


    with open(
        TIMELINE_PATH,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            timeline,
            file,
            indent=4
        )


    print(
        "[+] Saved timeline"
    )

def save_trends(trends):

    TREND_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )


    with open(
        TREND_PATH,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            trends,
            file,
            indent=4
        )


    print(
        "[+] Saved trend analysis"
    )

def save_map_events(events):

    MAP_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )


    with open(
        MAP_PATH,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            events,
            file,
            indent=4
        )


    print(
        "[+] Saved map events"
    )


def save_dashboard(dashboard):

    DASHBOARD_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )


    with open(
        DASHBOARD_PATH,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            dashboard,
            file,
            indent=4
        )


    print(
        "[+] Saved dashboard"
    )


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


    processed_events = analyze_threats(
        processed_events
    )


    processed_events = remove_duplicates(
        processed_events
    )
    

    all_events = append_events(
        processed_events
    )


    conflict_analysis = analyze_conflicts(
        all_events
    )


    regional_analysis = analyze_regions(
        all_events
    )


    timeline = generate_timeline(
        all_events
    )


    save_timeline(
        timeline
    )


    trends = analyze_trends(
        all_events
    )


    save_trends(
        trends
    )


    map_events = generate_map_events(
        all_events
    )


    save_map_events(
        map_events
    )

    intelligence_brief = generate_brief(
        all_events,
        regional_analysis
    )


    dashboard = generate_dashboard(
        all_events,
        intelligence_brief,
        trends
    )


    save_dashboard(
        dashboard
    )

    save_output(
        all_events,
        brief=intelligence_brief
    )

    export_dashboard(
        all_events,
        intelligence_brief,
        regional_analysis
    )

    print(
        "[+] Intelligence update complete"
    )



if __name__ == "__main__":

    main()