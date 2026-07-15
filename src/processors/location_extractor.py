"""
Location Processor

Prepares geographic data.
"""


def extract_location(event):


    location = event.get(
        "location",
        {}
    )


    return {

        "latitude":
        location.get(
            "latitude",
            0
        ),


        "longitude":
        location.get(
            "longitude",
            0
        )

    }