"""
Geolocation Processor

Attempts to assign geographic coordinates
to intelligence events.

Preserves existing sensor coordinates.

Sources:
- Event text matching
- Known location database

Future:
- NLP entity extraction
- Geocoding APIs
"""


LOCATION_DATABASE = {


    "ukraine": {

        "country":
        "Ukraine",

        "region":
        "Eastern Europe",

        "latitude":
        48.3794,

        "longitude":
        31.1656

    },


    "kyiv": {

        "country":
        "Ukraine",

        "region":
        "Eastern Europe",

        "city":
        "Kyiv",

        "latitude":
        50.4501,

        "longitude":
        30.5234

    },


    "russia": {

        "country":
        "Russia",

        "region":
        "Eastern Europe",

        "latitude":
        61.5240,

        "longitude":
        105.3188

    },


    "israel": {

        "country":
        "Israel",

        "region":
        "Middle East",

        "latitude":
        31.0461,

        "longitude":
        34.8516

    },


    "iran": {

        "country":
        "Iran",

        "region":
        "Middle East",

        "latitude":
        32.4279,

        "longitude":
        53.6880

    },


    "gaza": {

        "country":
        "Palestine",

        "region":
        "Middle East",

        "latitude":
        31.3547,

        "longitude":
        34.3088

    },


    "taiwan": {

        "country":
        "Taiwan",

        "region":
        "East Asia",

        "latitude":
        23.6978,

        "longitude":
        120.9605

    },


    "china": {

        "country":
        "China",

        "region":
        "East Asia",

        "latitude":
        35.8617,

        "longitude":
        104.1954

    }

}



def has_coordinates(event):

    location = event.get(
        "location",
        {}
    )


    latitude = location.get(
        "latitude",
        0
    )


    longitude = location.get(
        "longitude",
        0
    )


    return (

        latitude != 0

        and

        longitude != 0

    )



def geolocate_event(event):


    # Do not overwrite real sensor data

    if has_coordinates(event):

        return event



    searchable_text = " ".join([

        str(event.get(
            "title",
            ""
        )),

        str(event.get(
            "description",
            ""
        )),

        str(event.get(
            "actors",
            ""
        ))

    ]).lower()



    for location, data in LOCATION_DATABASE.items():


        if location in searchable_text:


            event["location"] = data


            return event



    return event




def apply_geolocation(events):


    processed = []


    for event in events:


        processed.append(

            geolocate_event(
                event
            )

        )


    return processed