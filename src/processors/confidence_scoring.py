"""
Confidence Scoring Engine

Calculates intelligence reliability.

Supports:
- single source strings
- multiple source lists
"""


def apply_confidence(events):


    for event in events:


        score = event.get(
            "confidence",
            50
        )


        source = event.get(
            "source",
            []
        )


        # Convert source list into searchable text

        if isinstance(source, list):

            source_text = " ".join(source).lower()

        else:

            source_text = str(source).lower()



        if "nasa" in source_text:

            score += 20



        if "opensky" in source_text:

            score += 15



        if "cisa" in source_text:

            score += 20



        if "acled" in source_text:

            score += 20



        if "reuters" in source_text:

            score += 15



        if score > 100:

            score = 100



        event["confidence"] = score



        if score >= 90:

            event["confidence_level"] = "verified"


        elif score >= 70:

            event["confidence_level"] = "high"


        elif score >= 40:

            event["confidence_level"] = "medium"


        else:

            event["confidence_level"] = "low"



    return events