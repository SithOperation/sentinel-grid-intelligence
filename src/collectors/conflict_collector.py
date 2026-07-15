"""
Conflict Intelligence Collector

Source:
GDELT Project

Collects global conflict-related events
and converts them into Sentinel Grid format.
"""

import requests
import datetime
import uuid


GDELT_URL = (
    "https://api.gdeltproject.org/api/v2/doc/doc"
)


def collect_conflicts():

    events = []

    query = (
        "war OR conflict OR missile OR "
        "airstrike OR artillery OR invasion"
    )


    params = {

        "query": query,

        "mode": "artlist",

        "maxrecords": 10,

        "format": "json"

    }


    try:

        response = requests.get(
            GDELT_URL,
            params=params,
            timeout=15
        )


        response.raise_for_status()


        data = response.json()


        articles = data.get(
            "articles",
            []
        )


        for article in articles:

            event = {

                "event_id":
                f"SG-{uuid.uuid4().hex[:8]}",


                "event_type":
                "conflict",


                "classification":
                "conflict_report",


                "priority":
                "high",


                "title":
                article.get(
                    "title",
                    "Conflict report"
                ),


                "description":
                article.get(
                    "seendate",
                    "Open source conflict intelligence"
                ),


                "source":
                [
                    article.get(
                        "domain",
                        "GDELT"
                    )
                ],


                "timestamp":
                datetime.datetime.now(
                    datetime.UTC
                ).isoformat(),


                "location":
                {

                    "country":
                    "Unknown",

                    "region":
                    "Unknown",

                    "latitude":
                    0,

                    "longitude":
                    0

                },


                "actors":
                [],


                "equipment":
                [],


                "verification":
                {

                    "confirmed":
                    False,

                    "source_count":
                    1

                }

            }


            events.append(event)


    except Exception as error:

        print(
            "[!] GDELT conflict collector error:",
            error
        )


    return events