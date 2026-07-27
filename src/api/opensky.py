"""
OpenSky Network API Client

Source:
OpenSky Network

Provides:
- aircraft ICAO
- callsign
- origin country
- position
- altitude
- velocity
- heading
"""

import requests

OPENSKY_URL = "https://opensky-network.org/api/states/all"


HEADERS = {"User-Agent": "Sentinel-Grid-Intelligence/1.0"}


def fetch():
    """
    Retrieve current aircraft states.
    """

    try:
        response = requests.get(OPENSKY_URL, headers=HEADERS, timeout=20)

        response.raise_for_status()

        data = response.json()

        return data.get("states", [])

    except Exception as error:
        print("[!] OpenSky API failed:", error)

        return []
