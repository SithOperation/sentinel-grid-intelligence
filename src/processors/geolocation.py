"""
Geolocation Processor

Attempts to assign geographic coordinates
to intelligence events.

Uses:
- event text matching
- known locations database

Future:
- NLP entity extraction
- geocoding APIs
"""


LOCATION_DATABASE = {

    "ukraine": {
        "country": "Ukraine",
        "latitude": 48.3794,
        "longitude": 31.1656
    },

    "kyiv": {
        "country": "Ukraine",
        "city": "Kyiv",
        "latitude": 50.4501,
        "longitude": 30.5234
    },

    "russia": {
        "country": "Russia",
        "latitude": 61.5240,
        "longitude": 105.3188
    },

    "israel": {
        "country": "Israel",
        "latitude": 31.0461,
        "longitude": 34.8516
    },

    "iran": {
        "country": "Iran",
        "latitude": 32.4279,
        "longitude": 53.6880
    },

    "gaza": {
        "country": "Palestine",
        "latitude": 31.3547,
        "longitude": 34.3088
    },

    "taiwan": {
        "country": "Taiwan",
        "latitude": 23.6978,
        "longitude": 120.9605
    },

    "china": {
        "country": "China",
        "latitude": 35.8617,
        "longitude": 104.1954
    }

}



def geolocate_event(event):

    """
    Attempts to assign location
    based on event text.
    """

    text = " ".join([

        str(event.get("title", "")),

        str(event.get("description", ""))

    ]).lower()


    for location, data in LOCATION_DATABASE.items():

        if location in text:

            event["location"] = data

            return event


    return event



def apply_geolocation(events):

    """

    Apply location processing
    to all events.

    """

    processed = []


    for event in events:

        processed.append(
            geolocate_event(event)
        )


    return processed