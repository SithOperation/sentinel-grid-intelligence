"""
Maritime Intelligence Collector

Source:
AISStream API

Tracks:
- vessel positions
- MMSI
- vessel name
- speed
- heading
- navigation activity

API authentication handled by:
src/api/aisstream.py

Requires:
AISSTREAM_API_KEY environment variable

Output:
Sentinel Grid standardized event format
"""


from api.aisstream import fetch
from models.event_model import create_event



def create_maritime_event(message):


    metadata = message.get(

        "MetaData",

        {}

    )


    position = message.get(

        "Message",

        {}

    )


    ship = position.get(

        "PositionReport",

        {}

    )



    latitude = ship.get(

        "Latitude",

        0

    )


    longitude = ship.get(

        "Longitude",

        0

    )



    event = create_event(

        event_type="maritime",

        classification="vessel_activity",

        priority="medium",

        title="AIS vessel activity detected",

        description="Open source maritime vessel observation",

        source=[

            "AISStream"

        ],

        location={


            "country":

            "Unknown",


            "region":

            "Unknown",


            "latitude":

            latitude,


            "longitude":

            longitude

        },

        confidence=75

    )



    event["vessel"] = {


        "mmsi":

        metadata.get(

            "MMSI",

            "UNKNOWN"

        ),



        "name":

        metadata.get(

            "ShipName",

            "UNKNOWN"

        ),



        "latitude":

        latitude,



        "longitude":

        longitude,



        "speed":

        ship.get(

            "Sog",

            0

        ),



        "heading":

        ship.get(

            "Cog",

            0

        )

    }



    event["verification"] = {


        "confirmed":

        True,


        "source_count":

        1

    }



    return event




def collect_maritime():


    events = []



    try:


        messages = fetch(

            limit=25

        )



        for message in messages:


            events.append(

                create_maritime_event(

                    message

                )

            )



        print(

            f"[+] AISStream collected {len(events)} vessel events"

        )



    except Exception as error:


        print(

            "[!] Maritime collector failed:",

            error

        )



    return events