"""
Dashboard Exporter

Creates frontend-ready intelligence data.
"""

import json
import datetime
from settings import load_config, resolve_project_path


CONFIG = load_config()
DASHBOARD_PATH = resolve_project_path(CONFIG["output"]["directory"]) / "dashboard.json"


def export_dashboard(
    events,
    intelligence_brief,
    regional_analysis
):

    dashboard = build_dashboard(events, intelligence_brief, regional_analysis)

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
        "[+] Dashboard data exported"
    )


def build_dashboard(events, intelligence_brief, regional_analysis):
    return {

        "generated":
            datetime.datetime.now(datetime.UTC).isoformat(),

        "summary": {

            "threat_level":
                intelligence_brief.get(
                    "global_threat_level",
                    "UNKNOWN"
                ),

            "total_events":
                len(events),

        },


        "critical_events":
            intelligence_brief.get(
                "critical_events",
                []
            ),


        "events":
            events,


        "regional_analysis":
            regional_analysis

    }
