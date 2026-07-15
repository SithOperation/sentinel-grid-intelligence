from collections import Counter


def analyze_trends(events):

    report = {

        "total_events": len(events),

        "event_types": {},

        "threat_levels": {},

        "priority_levels": {}

    }


    # Count event categories

    event_types = Counter(
        event.get(
            "event_type",
            "unknown"
        )
        for event in events
    )


    report["event_types"] = dict(
        event_types
    )


    # Count threat levels

    threat_levels = Counter(
        event.get(
            "threat_level",
            "unknown"
        )
        for event in events
    )


    report["threat_levels"] = dict(
        threat_levels
    )


    # Count priority

    priorities = Counter(
        event.get(
            "priority",
            "unknown"
        )
        for event in events
    )


    report["priority_levels"] = dict(
        priorities
    )


    return report