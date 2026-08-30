"""
Intelligence Brief Generator

Creates a summarized intelligence report
from processed events.

Output:
- global threat level
- critical events
- regional summaries
"""


def determine_global_level(events):

    highest_score = 0

    for event in events:
        score = event.get("threat_score", 0)

        highest_score = max(highest_score, score)

    if highest_score >= 85:
        return "CRITICAL"

    elif highest_score >= 60:
        return "HIGH"

    elif highest_score >= 35:
        return "ELEVATED"

    else:
        return "LOW"


def generate_brief(events, regional_data=None):

    brief = {
        "title": "SENTINEL GRID INTELLIGENCE BRIEF",
        "global_threat_level": determine_global_level(events),
        "total_events": len(events),
        "critical_events": [],
        "high_priority_events": [],
        "regional_summary": regional_data or {},
        "europe_security": {
            "top_developing": [],
            "nato_activity": [],
            "russian_activity": [],
            "poland_eastern_flank": [],
            "conflicting_reports": [],
            "newly_corroborated": [],
            "high_confidence": [],
        },
    }

    for event in events:
        level = event.get("threat_level", "LOW")

        summary = {
            "title": event.get("title", "Unknown"),
            "type": event.get("event_type", "Unknown"),
            "classification": event.get("classification", "Unknown"),
            "score": event.get("threat_score", 0),
        }

        if level == "CRITICAL":
            brief["critical_events"].append(summary)

        elif level == "HIGH":
            brief["high_priority_events"].append(summary)

        if event.get("event_type") == "europe_security":
            europe = brief["europe_security"]
            detail = {
                **summary,
                "status": event.get("status", "unverified"),
                "confidence": event.get("confidence", 0),
                "source_perspective": event.get("source_perspective"),
                "actor_reporting": event.get("actor_reporting", "UNKNOWN"),
                "actor_subject": event.get("actor_subject", "UNKNOWN"),
            }
            category = event.get("classification")
            if event.get("status") in {"developing", "officially_reported"}:
                europe["top_developing"].append(detail)
            if category == "nato_activity" or "NATO" in event.get("actors", []):
                europe["nato_activity"].append(detail)
            if category == "russian_activity" or "RUSSIA" in event.get("actors", []):
                europe["russian_activity"].append(detail)
            if event.get("location", {}).get("country") in {
                "Poland",
                "Poland/Lithuania",
            }:
                europe["poland_eastern_flank"].append(detail)
            if event.get("status") in {"disputed", "retracted"}:
                europe["conflicting_reports"].append(detail)
            if event.get("status") == "corroborated":
                europe["newly_corroborated"].append(detail)
            if event.get("confidence", 0) >= 75:
                europe["high_confidence"].append(detail)

    return brief
