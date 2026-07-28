# Source Feed migration rehearsal

The backend milestone uses an offline, temporary-directory rehearsal before any
website changes.

The rehearsal:

1. Generates two releases from the same retained events and reference clock.
2. Validates every manifest byte count and SHA-256 digest.
3. Verifies the source-feed and manifest publication IDs match.
4. Compares every legacy JSON top-level shape with the checked-in baseline.
5. Proves `map_events.json` and `timeline.json` remain bare arrays.
6. Confirms deterministic legacy artifacts remain byte-identical between runs.
7. Copies one complete release into a temporary website-data directory and
   revalidates it as one unit.
8. Uses the publisher failure-injection test to prove exact rollback.

The rehearsal never reads or writes the website repository.

