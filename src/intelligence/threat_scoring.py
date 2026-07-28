"""
Sentinel Grid Threat Scoring Engine

Assigns threat scores and threat levels
to normalized intelligence events.

Threat Levels:

LOW
MEDIUM
HIGH
CRITICAL

Factors:

- Event type
- Classification
- Priority
- Confidence
- Threat indicators
"""


def calculate_threat_score(event):

    score = 0

    event_type = event.get("event_type", "").lower()

    classification = event.get("classification", "").lower()

    title = event.get("title", "").lower()

    description = event.get("description", "").lower()

    priority = event.get("priority", "low").lower()

    confidence = event.get("confidence", 0)

    text = classification + " " + title + " " + description

    #
    # Base event weighting
    #

    event_weights = {
        "conflict": 40,
        "humanitarian": 25,
        "wildfire": 20,
        "flood": 20,
        "tropical_cyclone": 25,
        "natural_hazard": 15,
        "earthquake": 15,
        "volcano": 20,
        "weather_alert": 15,
    }

    score += event_weights.get(event_type, 0)

    if event_type == "earthquake":
        details = event.get("earthquake", {})
        magnitude = details.get("magnitude")
        if isinstance(magnitude, (int, float)):
            score += 5 if magnitude >= 4 else 0
            score += 10 if magnitude >= 5 else 0
            score += 15 if magnitude >= 6 else 0
            score += 15 if magnitude >= 7 else 0
        if details.get("tsunami"):
            score += 15
        if str(details.get("alert", "")).casefold() in {"orange", "red"}:
            score += 15

    if event_type == "volcano":
        volcanic_terms = (
            "eruption",
            "ash plume",
            "evacuation",
            "aviation warning",
            "pyroclastic",
            "lava flow",
            "explosive",
        )
        score += min(30, sum(5 for term in volcanic_terms if term in text))

    if event_type == "weather_alert":
        weather = event.get("weather", {})
        severity_bonus = {
            "Extreme": 30,
            "Severe": 20,
            "Moderate": 10,
            "Minor": 0,
            "Unknown": 0,
        }
        score += severity_bonus.get(weather.get("severity"), 0)
        if weather.get("urgency") == "Immediate":
            score += 10
        if weather.get("certainty") == "Observed":
            score += 5

    #
    # Classification weighting
    #

    high_risk_terms = [
        "attack",
        "strike",
        "airstrike",
        "military",
        "troops",
        "armed",
        "breach",
        "malware",
        "ransomware",
        "exploit",
        "vulnerability",
    ]

    critical_terms = [
        "nuclear",
        "ballistic",
        "missile",
        "invasion",
        "zero-day",
        "chemical",
        "biological",
        "mass casualty",
    ]

    for term in high_risk_terms:
        if term in text:
            score += 10

    for term in critical_terms:
        if term in text:
            score += 20

    #
    # Priority scoring
    #

    if priority == "critical":
        score += 25

    elif priority == "high":
        score += 15

    elif priority == "medium":
        score += 5

    #
    # Confidence scoring
    #

    if confidence >= 90:
        score += 15

    elif confidence >= 70:
        score += 10

    elif confidence >= 50:
        score += 5

    #
    # Maximum score
    #

    score = min(score, 100)

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
        analyzed.append(assign_threat_level(event))

    return analyzed
