# Static data contract

Sentinel Grid publishes a validated group of JSON files to the configured
output directory. Contract version `1.0` preserves the existing array formats
used by the map and timeline while adding release metadata.

## Publication protocol

All files are serialized and validated in a staging directory. They are moved
into the output directory only after the whole release passes validation.
`manifest.json` is replaced last and is the authoritative completion signal.
A frontend that polls for updates should fetch the manifest first and refresh
its datasets only when `publication_id` changes.

## Files

- `manifest.json`: publication ID, contract version, generation time, byte
  size, and SHA-256 digest of every artifact.
- `health.json`: source status, collection duration, source event counts, and
  overall healthy/degraded state.
- `world_events.json`: versioned complete retained event collection.
- `map_events.json`: bounded array containing only valid geographic points.
- `timeline.json`: chronological event summaries.
- `trends.json`: distributions and aggregate confidence.
- `intelligence_brief.json`: threat and regional summary.
- `dashboard.json`: frontend summary plus retained event details.

The browser must treat all strings as untrusted text and use text rendering,
not raw HTML injection. URLs are restricted to HTTP and HTTPS during backend
normalization.

## Compatibility

The frontend should reject an unknown major `schema_version`. Additive fields
within version `1.x` are backward-compatible. Removing or renaming fields
requires a new major contract version.

## Exact version 1.0 shapes

`manifest.json`:

```json
{
  "schema_version": "1.0",
  "publication_id": "32-character UUID4 hex value",
  "generated": "UTC ISO-8601 timestamp",
  "files": {
    "map_events.json": {
      "bytes": 64842,
      "sha256": "64-character lowercase SHA-256 digest"
    }
  }
}
```

The `files` object contains all seven non-manifest artifacts. A new random
publication ID is created only after every artifact has serialized, passed its
contract, and passed its configured size limit. Files are replaced from the
staging directory and `manifest.json` is replaced last.

`health.json`:

```json
{
  "schema_version": "1.0",
  "generated": "UTC ISO-8601 timestamp",
  "status": "healthy",
  "degraded": false,
  "stale": false,
  "stale_after_minutes": 390,
  "published_event_count": 162,
  "freshness": {
    "oldest_event": "UTC ISO-8601 timestamp or null",
    "newest_event": "UTC ISO-8601 timestamp or null",
    "age_minutes": 12.5
  },
  "sources": [
    {
      "source": "nasa_eonet",
      "enabled": true,
      "status": "ok",
      "event_count": 25,
      "duration_ms": 412,
      "checked_at": "UTC ISO-8601 timestamp",
      "last_success": "UTC ISO-8601 timestamp or null",
      "error": null
    }
  ]
}
```

Source status is `ok`, `no_data`, `disabled`, or `not_checked`. Offline
publication uses `not_checked` and adds a human-readable `note`. The optional
`error` value is reserved for a sanitized collector error. Any non-`ok` enabled
source or stale event data makes the release degraded. Data is stale when the
newest valid event is older than `output.stale_after_minutes` (390 minutes by
default), or when no valid event timestamp exists.

`dashboard.json` uses `summary.threat_level` and `summary.total_events`.

Each `map_events.json` element contains `event_id`, `type`, `title`,
`description`, `latitude`, `longitude`, `priority`, `threat_level`,
`confidence`, and `timestamp`. Coordinates are numeric decimal degrees.
Latitude must be between -90 and 90; longitude must be between -180 and 180.
The placeholder pair `(0, 0)` and malformed points are excluded. Legitimate
points on only the equator or only the prime meridian remain valid.

## Offline publication

To regenerate a complete validated release from the retained database without
network calls or API credentials:

```powershell
$env:PYTHONPATH = "src"
.\venv\Scripts\python.exe src\main.py --publish-existing
```

This deliberately reports source checks as `not_checked` and overall coverage
as degraded. A collector returning no data also produces a degraded release
using retained events. A contract, serialization, or size-limit failure does
not replace the manifest; consumers must retain their last verified release.
