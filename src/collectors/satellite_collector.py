"""
Satellite / Earth Observation Intelligence Collector

Source:
- NASA EONET API

Tracks:
- wildfire events
- volcanic activity
- storms
- natural events

Output:
Sentinel Grid standardized event format
"""


from api.nasa_eonet import fetch
from models.event_model import create_event



def create_satellite_event(event):


    categories = event.get(
        "categories",
        []
    )


    geometry = event.get(
        "geometry",
        []
    )


    coordinates = {

        "latitude": 0,

        "longitude": 0

    }



    if geometry:


        latest = geometry[-1]


        coords = latest.get(
            "coordinates",
            []
        )


        if len(coords) >= 2:


            coordinates = {


                "longitude":

                coords[0],


                "latitude":

                coords[1]

            }



    category_name = (

        categories[0].get(
            "title"
        )

        if categories

        else

        "Earth observation event"

    )



    event_record = create_event(

        event_type="satellite",

        classification="earth_observation",

        priority="medium",

        title=event.get(

            "title",

            "Satellite observation event"

        ),

        description=category_name,

        source=[

            "NASA EONET"

        ],

        location={


            "country":

            "Unknown",


            "region":

            "Unknown",


            "latitude":

            coordinates["latitude"],


            "longitude":

            coordinates["longitude"]

        },

        confidence=80

    )



    event_record["observation"] = {


        "category":

        category_name,


        "event_id":

        event.get(
            "id"
        )

    }

    if geometry and geometry[-1].get("date"):
        event_record["timestamp"] = geometry[-1]["date"]

    event_record["url"] = event.get("link", "")



    event_record["verification"] = {


        "confirmed":

        True,


        "source_count":

        1

    }



    return event_record




def collect_satellite():


    events = []



    try:


        nasa_events = fetch()



        for event in nasa_events[:25]:


            events.append(

                create_satellite_event(

                    event

                )

            )



        print(

            f"[+] NASA satellite events collected {len(events)} events"

        )



    except Exception as error:


        print(

            "[!] NASA satellite events failed:",

            error

        )



    return events
