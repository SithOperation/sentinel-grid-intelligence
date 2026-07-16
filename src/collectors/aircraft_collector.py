"""
Aircraft Intelligence Collector

Source:
OpenSky Network

Collects:
- aircraft position
- altitude
- speed
- heading
- callsign
- origin country

Future:
- ADS-B Exchange
- military aircraft classification
- conflict zone correlation

Output:
Sentinel Grid standardized event format
"""


from api.opensky import fetch
from models.event_model import create_event



MAX_AIRCRAFT = 50



def safe_value(value, default="UNKNOWN"):

    if value is None:

        return default

    return value




def create_aircraft_event(aircraft):


    latitude = aircraft[6]

    longitude = aircraft[5]



    event = create_event(

        event_type="aircraft",

        classification="air_activity",

        priority="medium",

        title="Aircraft activity detected",

        description="Open source ADS-B aircraft observation",

        source=[

            "OpenSky Network"

        ],

        location={


            "country":

            safe_value(
                aircraft[2]
            ),


            "region":

            "Unknown",


            "latitude":

            latitude,


            "longitude":

            longitude

        },

        confidence=70

    )



    event["aircraft"] = {


        "icao":

        safe_value(
            aircraft[0]
        ),



        "callsign":

        safe_value(

            aircraft[1].strip()

            if aircraft[1]

            else None

        ),



        "origin_country":

        safe_value(
            aircraft[2]
        ),



        "altitude":

        safe_value(
            aircraft[7],
            0
        ),



        "velocity":

        safe_value(
            aircraft[9],
            0
        ),



        "heading":

        safe_value(
            aircraft[10],
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




def collect_aircraft():


    events = []



    try:


        aircraft_list = fetch()



        for aircraft in aircraft_list[:MAX_AIRCRAFT]:


            if len(aircraft) < 11:

                continue



            if aircraft[5] is None:

                continue



            if aircraft[6] is None:

                continue



            events.append(

                create_aircraft_event(

                    aircraft

                )

            )



        print(

            f"[+] OpenSky aircraft collected {len(events)} events"

        )



    except Exception as error:


        print(

            "[!] OpenSky aircraft collector failed:",

            error

        )



    return events