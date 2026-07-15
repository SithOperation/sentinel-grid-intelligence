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

from yaml import events


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
from intelligence.threat_scoring import analyze_threats
from intelligence.conflict_analysis import analyze_conflicts
from intelligence.regional_analysis import analyze_regions
from intelligence.intelligence_brief import generate_brief


# Output location

OUTPUT_PATH = Path(
    "data/output/world_events.json"
)

BRIEF_PATH = Path(
    "data/output/intelligence_brief.json"
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
        f"[+] Saved {len(events)} events"
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



    conflict_analysis = analyze_conflicts(
        processed_events
)



    regional_analysis = analyze_regions(
        processed_events
)



    intelligence_brief = generate_brief(
        processed_events,
        regional_analysis
)



    save_output(
        processed_events,
        brief=intelligence_brief
    )


    print(
        "[+] Intelligence update complete"
    )



if __name__ == "__main__":

    main()