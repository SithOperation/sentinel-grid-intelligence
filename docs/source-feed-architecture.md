# Sentinel Source Feed architecture

The Source Feed is an optional discovery capability inside a mandatory,
versioned publication artifact. `source_feed.json` exists in every release,
even when no adapter returns a usable item.

> Feed inclusion is based on source usefulness. Map inclusion is based on
> defensible event geography. Claim verification is evaluated independently
> from location confidence.

The map remains Sentinel's primary interface. Location confidence, claim
confidence, and event-association confidence are separate fields. An adapter
failure degrades source-feed health and cannot prevent core Sentinel
publication.

All public records use the release publication ID from `manifest.json`.
Internal response evidence is bounded and never published. Active feed
retention is based on `published_at`; a documented discovery-time fallback is
permitted only when the adapter cannot establish an original timestamp.

