"""
Humanitarian Intelligence Collector

Source:
- GDACS Global Disaster Alert and Coordination System

Tracks:
- earthquakes
- floods
- storms
- volcanoes
- major disasters

Output:
Sentinel Grid standardized event format
"""


from api.gdacs import fetch
from models.event_model import create_event



def create_humanitarian_event(item):


    title = (

        item.findtext(
            "title"
        )

        or

        "Global disaster event"

    )


    description = (

        item.findtext(
            "description"
        )

        or

        ""

    )


    link = (

        item.findtext(
            "link"
        )

        or

        ""

    )



    event = create_event(

        event_type="humanitarian",

        classification="disaster_alert",

        priority="high",

        title=title,

        description=description[:500],

        source=[

            "GDACS"

        ],

        confidence=80

    )



    event["url"] = link



    event["crisis"] = {


        "type":

        "global_disaster_alert",


        "severity":

        "unknown"

    }



    event["verification"] = {


        "confirmed":

        True,


        "source_count":

        1

    }



    return event




def collect_humanitarian():


    events = []



    try:


        disaster_items = fetch()



        for item in disaster_items:


            events.append(

                create_humanitarian_event(

                    item

                )

            )



            if len(events) >= 10:

                break



        print(

            f"[+] GDACS humanitarian collected {len(events)} events"

        )



    except Exception as error:


        print(

            "[!] GDACS humanitarian collector failed:",

            error

        )



    return events