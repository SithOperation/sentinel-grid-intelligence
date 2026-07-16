"""
Regional Analysis Engine

Groups intelligence events by geographic region.

Creates:
- regional activity summaries
- event counts
- threat levels
- activity levels
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



    europe = [

        "ukraine",
        "russia",
        "poland",
        "belarus",
        "romania",
        "germany",
        "france",
        "united kingdom",
        "finland",
        "sweden",
        "norway"

    ]



    middle_east = [

        "iran",
        "iraq",
        "israel",
        "syria",
        "lebanon",
        "yemen",
        "saudi arabia",
        "jordan"

    ]



    indo_pacific = [

        "china",
        "taiwan",
        "japan",
        "north korea",
        "south korea",
        "philippines",
        "australia"

    ]



    africa = [

        "sudan",
        "ethiopia",
        "somalia",
        "nigeria",
        "libya",
        "mali"

    ]



    americas = [

        "united states",
        "usa",
        "canada",
        "mexico",
        "brazil",
        "colombia"

    ]



    if country in europe:

        return "Europe"



    if country in middle_east:

        return "Middle East"



    if country in indo_pacific:

        return "Indo-Pacific"



    if country in africa:

        return "Africa"



    if country in americas:

        return "Americas"



    return "Unknown"





def determine_activity_level(event_count):


    if event_count >= 25:

        return "SEVERE"



    if event_count >= 10:

        return "ELEVATED"



    if event_count >= 3:

        return "ACTIVE"



    return "LOW"





def determine_threat_level(score):


    if score >= 85:

        return "CRITICAL"



    if score >= 60:

        return "HIGH"



    if score >= 35:

        return "MEDIUM"



    return "LOW"





def analyze_regions(events):


    regions = {}



    for event in events:


        region = determine_region(
            event
        )



        if region not in regions:


            regions[region] = {


                "region":

                region,


                "event_count":

                0,


                "highest_threat":

                "LOW",


                "threat_score":

                0,


                "activity_level":

                "LOW",


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



    for region, data in regions.items():


        data["highest_threat"] = determine_threat_level(

            data["threat_score"]

        )



        data["activity_level"] = determine_activity_level(

            data["event_count"]

        )



    return regions