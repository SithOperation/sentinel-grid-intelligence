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


        score = event.get(
            "threat_score",
            0
        )


        if score > highest_score:

            highest_score = score



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


        "title":

        "SENTINEL GRID INTELLIGENCE BRIEF",



        "global_threat_level":

        determine_global_level(events),



        "total_events":

        len(events),



        "critical_events":

        [],



        "high_priority_events":

        [],



        "regional_summary":

        regional_data or {}

    }



    for event in events:


        level = event.get(
            "threat_level",
            "LOW"
        )


        summary = {


            "title":

            event.get(
                "title",
                "Unknown"
            ),


            "type":

            event.get(
                "event_type",
                "Unknown"
            ),


            "classification":

            event.get(
                "classification",
                "Unknown"
            ),


            "score":

            event.get(
                "threat_score",
                0
            )

        }



        if level == "CRITICAL":


            brief["critical_events"].append(
                summary
            )



        elif level == "HIGH":


            brief["high_priority_events"].append(
                summary
            )



    return brief