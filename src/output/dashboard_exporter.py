"""
Dashboard Exporter

Creates frontend-ready intelligence data.
"""

from pathlib import Path
import json
import datetime


DASHBOARD_PATH = Path(
    "data/output/dashboard.json"
)


def export_dashboard(
    events,
    intelligence_brief,
    regional_analysis
):

    dashboard = {

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