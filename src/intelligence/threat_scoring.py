"""
Threat Scoring Engine

Assigns threat levels to intelligence events.

Levels:
LOW
MEDIUM
HIGH
CRITICAL
"""


def calculate_threat_score(event):


    score = 0


    event_type = event.get(
        "event_type",
        ""
    )


    classification = event.get(
        "classification",
        ""
    )


    confidence = event.get(
        "confidence",
        0
    )


    priority = event.get(
        "priority",
        "low"
    )



    # Event category scoring

    if event_type == "conflict":

        score += 40


    elif event_type == "cyber":

        score += 30


    elif event_type == "maritime":

        score += 20


    elif event_type == "aircraft":

        score += 20


    elif event_type == "satellite":

        score += 15


    elif event_type == "humanitarian":

        score += 25



    # Classification scoring

    dangerous_terms = [

        "artillery",

        "missile",

        "strike",

        "attack",

        "ransomware",

        "invasion",

        "cyber_attack"

    ]


    for term in dangerous_terms:

        if term in classification:

            score += 20



    # Confidence weighting

    if confidence >= 80:

        score += 20


    elif confidence >= 50:

        score += 10



    # Priority weighting

    if priority == "high":

        score += 20


    elif priority == "medium":

        score += 10



    if score > 100:

        score = 100



    return score




def assign_threat_level(event):


    score = calculate_threat_score(event)


    event["threat_score"] = score



    if score >= 85:

        event["threat_level"] = "CRITICAL"


    elif score >= 60:

        event["threat_level"] = "HIGH"


    elif score >= 35:

        event["threat_level"] = "MEDIUM"


    else:

        event["threat_level"] = "LOW"



    return event




def analyze_threats(events):


    analyzed = []


    for event in events:

        analyzed.append(
            assign_threat_level(event)
        )


    return analyzed