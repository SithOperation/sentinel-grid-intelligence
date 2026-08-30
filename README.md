# Sentinel Grid Intelligence

Sentinel Grid Intelligence is a standalone, free-to-run, location-based
intelligence pipeline. It collects recent physical events from public sources,
normalizes them into one canonical event model, and atomically publishes
validated static JSON for a MapLibre frontend.

Sentinel covers:

- USGS earthquakes
- NASA EONET volcanoes, wildfires, floods, severe storms, and selected hazards
- U.S. National Weather Service active alerts
- GDACS global disasters and humanitarian emergencies
- conflict reports extracted from public news feeds
- explicitly configured public X status reports with operator-supplied,
  validated coordinates

Sentinel does not collect cyber or AI news, track aircraft, track ships, or use
AIS. Cyber and AI reporting belongs to the separate AI Cyber Digest project.
Sentinel has no dependency on deleted disaster or weather repositories and
does not require paid APIs.

## Pipeline

```text
USGS + NASA EONET + NWS + GDACS + conflict feeds + public X URLs
    -> normalization
    -> classification and geolocation validation
    -> conservative deduplication
    -> confidence and threat scoring
    -> rolling 72-hour UTC retention
    -> analysis
    -> validated atomic publication
```

NASA EONET is fetched once per run and the response is split into volcano and
selected natural-event collectors. Provider failures are isolated and reported
in `health.json`; one outage does not stop other collectors.

## Setup

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
$env:PYTHONPATH = "src"
.\venv\Scripts\python.exe src\main.py
```

Configuration lives in `config.yaml`. USGS, EONET, NWS, GDACS, public news
feeds, and public X page metadata require no secret. X collection reads only
explicit public status URLs in `sources.x.urls`; it does not use the paid X API
or crawl accounts.

Every event-bearing artifact derives from the same canonical retained list.
The rolling UTC cutoff is inclusive at exactly 72 hours. Malformed, future, and
older timestamps are discarded. Active NWS alerts use collection time as their
canonical timestamp and preserve provider lifecycle timestamps in metadata;
expired alerts are always removed.

Map output accepts only supported physical-event types with valid coordinates.
It rejects `(0, 0)`, invalid points, imprecise country-center conflict matches,
and events without trustworthy coordinates. Such events may remain in non-map
outputs only when they still fit Sentinel's location-based mission.

## Publication

### Europe / NATO / Russia public reporting

Sentinel correlates public NATO, European security-media, and Reddit RSS/Atom
reporting through a provenance-aware collector. Reddit reposts of one external
article remain separate observations but never become false corroboration.
Locations use controlled city/region/country coordinates, and unlocated reports
remain off-map. Configure feeds and term groups in
`config/europe_security.yaml`; see `docs/europe-security-collector.md` for the
confidence, perspective, polling, and extension model.

### Near-live weather

The scheduled publisher collects official active National Weather Service alerts every 15 minutes. Expired, malformed, duplicate, and administrative test messages are rejected before publication. A failed provider request does not erase the last validated website publication; the next successful run replaces it through the normal atomic publication and repository-dispatch flow. No paid weather API is required.

Generated artifacts are written under `data/output`; retained canonical events
are stored in `data/database/events.json`. A release is staged and validated
before replacement, with `manifest.json` replaced last as the completion
signal. See `docs/data-contract.md`.

Publish retained data without network calls:

```powershell
$env:PYTHONPATH = "src"
.\venv\Scripts\python.exe src\main.py --publish-existing
```

Validate the current publication:

```powershell
.\venv\Scripts\python.exe src\main.py --validate-existing
```

Deliberately clear only known generated artifacts, the retained database, and
the configured X cache:

```powershell
.\venv\Scripts\python.exe src\main.py --reset-generated-data
```

The reset command never scans for or deletes arbitrary JSON files.

## Verification

```powershell
$env:PYTHONPATH = "src"
.\venv\Scripts\python.exe -m ruff check src tests
.\venv\Scripts\python.exe -m ruff format --check src tests
.\venv\Scripts\python.exe -m pyright src tests
.\venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Disclaimer

Sentinel uses publicly available information for research, education, and
open-source intelligence analysis. It does not provide classified intelligence.
