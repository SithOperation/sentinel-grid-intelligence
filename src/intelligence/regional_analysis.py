"""
Regional Analysis Engine

Groups intelligence events by geographic region.

Creates:
- regional activity summaries
- event counts
- threat levels
"""


def determine_region(event):


    location = event.get(
        "location",
        {}
    )


    country = location.get(
        "country",
        "Unknown"
    ).lower()



    # Future expansion:
    # Add country databases later


    europe = [

        "ukraine",

        "russia",

        "poland",

        "belarus",

        "romania"

    ]


    middle_east = [

        "iran",

        "iraq",

        "israel",

        "syria",

        "lebanon",

        "yemen"

    ]


    asia = [

        "china",

        "taiwan",

        "japan",

        "north korea",

        "south korea"

    ]



    if country in europe:

        return "Europe"



    if country in middle_east:

        return "Middle East"



    if country in asia:

        return "Indo-Pacific"



    return "Unknown"





def analyze_regions(events):


    regions = {}



    for event in events:


        region = determine_region(event)



        if region not in regions:


            regions[region] = {


                "event_count":

                0,


                "highest_threat":

                "LOW",


                "threat_score":

                0,


                "events":

                []

            }



        regions[region]["event_count"] += 1



        regions[region]["events"].append(

            event.get(
                "title",
                "Unknown Event"
            )

        )



        score = event.get(
            "threat_score",
            0
        )



        if score > regions[region]["threat_score"]:

            regions[region]["threat_score"] = score



    # Convert scores to levels


    for region in regions:


        score = regions[region]["threat_score"]



        if score >= 85:

            regions[region]["highest_threat"] = "CRITICAL"


        elif score >= 60:

            regions[region]["highest_threat"] = "HIGH"


        elif score >= 35:

            regions[region]["highest_threat"] = "MEDIUM"


        else:

            regions[region]["highest_threat"] = "LOW"



    return regions