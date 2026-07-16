"""
Conflict Analysis Engine

Analyzes military/conflict events.

Creates:
- conflict activity level
- indicators
- regional summaries
- threat assessment
"""


CONFLICT_INDICATORS = [

    "missile",

    "airstrike",

    "strike",

    "attack",

    "artillery",

    "troops",

    "invasion",

    "battle",

    "ceasefire",

    "military",

    "weapon"

]



def analyze_conflicts(events):


    conflict_events = [

        event

        for event in events

        if event.get(
            "event_type"
        ) == "conflict"

    ]



    analysis = {


        "total_conflict_events":

        len(conflict_events),


        "activity_level":

        "LOW",


        "indicators":

        [],


        "regions":

        {},


        "assessment":

        "No significant conflict indicators detected"

    }



    if not conflict_events:

        return analysis



    indicator_set = set()



    region_count = {}



    highest_threat = 0



    for event in conflict_events:


        text = (

            str(event.get(
                "title",
                ""
            ))

            +

            str(event.get(
                "description",
                ""
            ))

        ).lower()



        for indicator in CONFLICT_INDICATORS:


            if indicator in text:

                indicator_set.add(

                    indicator

                )



        threat_score = event.get(

            "threat_score",

            0

        )



        if threat_score > highest_threat:

            highest_threat = threat_score



        location = event.get(

            "location",

            {}

        )


        region = location.get(

            "region",

            "Unknown"

        )


        region_count[region] = (

            region_count.get(

                region,

                0

            )

            +

            1

        )



    analysis["indicators"] = list(

        indicator_set

    )



    analysis["regions"] = region_count



    if highest_threat >= 85:


        analysis["activity_level"] = "CRITICAL"



    elif highest_threat >= 60:


        analysis["activity_level"] = "HIGH"



    else:


        analysis["activity_level"] = "ELEVATED"



    analysis["assessment"] = (

        f"{len(conflict_events)} conflict events analyzed. "

        f"Indicators detected: "

        f"{', '.join(analysis['indicators']) or 'none'}."

    )



    return analysis