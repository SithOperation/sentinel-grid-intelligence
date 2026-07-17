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

- `manifest.json`: publication ID, contract version, generation time, and byte
  size of every artifact.
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
