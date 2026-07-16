"""
AISStream API Client

Source:
AISStream WebSocket API

Provides:
- vessel positions
- MMSI
- ship names
- speed
- heading
"""


import os
import json
import websocket


AISSTREAM_URL = (
    "wss://stream.aisstream.io/v0/stream"
)



def fetch(limit=25):

    """
    Retrieve AIS vessel messages.

    Returns:
        list of AIS message dictionaries
    """


    events = []


    api_key = os.getenv(
        "AISSTREAM_API_KEY"
    )


    if not api_key:

        print(
            "[!] AISStream API key missing"
        )

        return events



    try:


        ws = websocket.create_connection(

            AISSTREAM_URL,

            timeout=20

        )


        subscribe = {


            "APIKey":

            api_key,


            "BoundingBoxes":

            [

                [

                    [

                        -90,

                        -180

                    ],

                    [

                        90,

                        180

                    ]

                ]

            ]

        }



        ws.send(

            json.dumps(
                subscribe
            )

        )



        while len(events) < limit:


            message = ws.recv()


            data = json.loads(
                message
            )


            if "Message" in data:

                events.append(
                    data
                )



        ws.close()



    except Exception as error:


        print(

            "[!] AISStream API failed:",

            error

        )



    return events