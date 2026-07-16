"""
NASA EONET API Client

Source:
NASA Earth Observatory Natural Event Tracker

Provides:
- wildfire events
- volcanic activity
- storms
- natural earth observations
"""


import requests


EONET_URL = (

    "https://eonet.gsfc.nasa.gov/api/v3/events"

)


HEADERS = {

    "User-Agent":

    "Sentinel-Grid-Intelligence/1.0"

}



def fetch():

    """
    Retrieve NASA EONET events.

    Returns:
        list of NASA event objects
    """


    try:

        response = requests.get(

            EONET_URL,

            headers=HEADERS,

            timeout=20

        )


        response.raise_for_status()


        data = response.json()


        return data.get(

            "events",

            []

        )


    except Exception as error:


        print(

            "[!] NASA EONET API failed:",

            error

        )


        return []