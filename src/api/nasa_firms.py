"""
NASA FIRMS API Wrapper

Source:
NASA Fire Information for Resource Management System

Provides:
- wildfire detections
- thermal anomalies
- satellite observations
"""


import os
import requests
from dotenv import load_dotenv


load_dotenv()


NASA_KEY = os.getenv(
    "NASA_FIRMS_KEY"
)


BASE_URL = (
    "https://firms.modaps.eosdis.nasa.gov/api/"
    "area/csv/"
)


def fetch(
    area="world",
    days=1
):

    if not NASA_KEY:
        print(
            "[!] NASA FIRMS API key missing"
        )
        return []


    url = (
        BASE_URL
        +
        f"{NASA_KEY}/VIIRS_SNPP_NRT/{area}/{days}"
    )


    try:

        response = requests.get(
            url,
            timeout=30
        )


        response.raise_for_status()


        lines = response.text.splitlines()


        if len(lines) < 2:
            return []


        headers = lines[0].split(",")


        events = []


        for line in lines[1:100]:

            values = line.split(",")


            event = dict(
                zip(
                    headers,
                    values
                )
            )


            events.append(
                event
            )


        return events


    except Exception as error:

        print(
            "[!] NASA FIRMS failed:",
            error
        )

        return []