# Pending score-mapping selections

A Product Reality run showed that confirming one score-role mapping refreshed the desktop project and cleared still-unconfirmed selections in the other Bass/Lead/Rhythm dropdowns. The persisted mapping contract was correct; the loss occurred only in transient UI state.

The desktop mapping refresh now follows two authority rules:

1. A persisted score mapping is authoritative and is rendered from the current score contract, including its confirmed/review-required marker.
2. When a role has no persisted mapping yet, a user's current dropdown selection is preserved across refresh only if that exact track label still exists in the current score inventory. If the score changes and the selected track disappears, the pending selection is cleared.

This prevents a successful confirmation of one role from destroying the user's pending choices for the other roles while still failing closed on stale score-track identity.

## Safety boundary

Preserving a dropdown value is not human confirmation and creates no provenance authority. Only the existing explicit **Confirm** action writes a score-role mapping. This change does not auto-map tracks, fan out arrangements, alter source data, accept musical decisions, package CDLC, modify the live Rocksmith installation, or interact with NoCableLauncher.
