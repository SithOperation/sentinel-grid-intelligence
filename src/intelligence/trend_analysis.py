"""
Sentinel Grid Trend Analysis Engine

Analyzes intelligence activity trends.

Produces:
- event type distribution
- threat level distribution
- priority distribution
- source activity
- geographic activity
- confidence averages
"""


from collections import Counter





def analyze_trends(events):


    report = {


        "total_events":

        len(events),



        "event_types":

        {},



        "threat_levels":

        {},



        "priority_levels":

        {},



        "sources":

        {},



        "regions":

        {},



        "average_confidence":

        0

    }



    if not events:

        return report




    # ----------------------------
    # Event Type Trends
    # ----------------------------


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




    # ----------------------------
    # Threat Trends
    # ----------------------------


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




    # ----------------------------
    # Priority Trends
    # ----------------------------


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




    # ----------------------------
    # Source Analysis
    # ----------------------------


    source_counter = Counter()



    for event in events:


        sources = event.get(

            "source",

            []

        )


        if isinstance(
            sources,
            list
        ):


            for source in sources:

                source_counter[source] += 1



        else:

            source_counter[str(sources)] += 1




    report["sources"] = dict(

        source_counter

    )





    # ----------------------------
    # Regional Activity
    # ----------------------------


    region_counter = Counter()



    for event in events:


        location = event.get(

            "location",

            {}

        )


        region = location.get(

            "country",

            "Unknown"

        )


        region_counter[region] += 1



    report["regions"] = dict(

        region_counter

    )





    # ----------------------------
    # Confidence Analysis
    # ----------------------------


    confidence_total = 0



    for event in events:


        confidence_total += event.get(

            "confidence",

            0

        )



    report["average_confidence"] = round(

        confidence_total / len(events),

        2

    )



    return report