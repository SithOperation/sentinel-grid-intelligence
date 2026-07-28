"""
Dashboard Exporter

Creates frontend-ready intelligence data.
"""

import datetime


def build_dashboard(events, intelligence_brief, regional_analysis, generated=None):
    return {
        "generated": (generated or datetime.datetime.now(datetime.UTC)).isoformat(),
        "summary": {
            "threat_level": intelligence_brief.get("global_threat_level", "UNKNOWN"),
            "total_events": len(events),
        },
        "critical_events": intelligence_brief.get("critical_events", []),
        "events": events,
        "regional_analysis": regional_analysis,
    }
