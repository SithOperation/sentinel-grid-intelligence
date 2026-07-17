from datetime import datetime, timezone


def generate_dashboard(
    events,
    brief,
    trends
):

    dashboard = {

        "generated": datetime.now(timezone.utc).isoformat(),

        "summary": {

            "total_events": len(events),

            "global_threat_level":
                brief.get(
                    "global_threat_level",
                    "UNKNOWN"
                )

        },

        "event_counts":
            trends.get(
                "event_types",
                {}
            ),

        "threat_distribution":
            trends.get(
                "threat_levels",
                {}
            ),

        "priority_distribution":
            trends.get(
                "priority_levels",
                {}
            ),

        "critical_events": 
            brief.get(
                "critical_events",
                []
            ),

        "regional_summary":
            brief.get(
                "regional_summary",
                {}
            )

    }


    return dashboard
