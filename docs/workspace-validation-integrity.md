# Song Workspace validation-report integrity

Song Workspace must distinguish **validation has not run** from **a persisted validation artifact exists but is unreadable or invalid**.

## Contract

- No validation report on disk is represented as `NOT_RUN`.
- A present report that cannot be read or parsed as the current `ValidationReport` schema is represented as `INVALID`.
- A configured arrangement with an invalid persisted validation report blocks overall workspace health.
- Existing Rocksmith XML cannot report ready while the corresponding validation report is invalid.
- The combined review queue receives a high-priority `invalid_validation_report` failure that instructs the user to re-run validation.
- Song Workspace remains read-only: it does not delete, repair, rewrite, or silently accept the malformed report.

## Root cause addressed

Previously `_read_validation()` returned `None` for both a missing report and a malformed/truncated report. That collapsed two different authority states into `NOT_RUN` and could hide corrupted persisted review evidence behind old downstream XML.

The prevention rule is: **presence plus parse failure is an explicit blocking integrity state, not absence**. Persisted authority/derivative artifacts should never be downgraded to a harmless missing state merely because the reader failed.

This follows the recurring-defect engineering memory in #193 and fixes #173.

## Safety boundary

This change does not approve source rights, mappings, timing, fingering, techniques, tones, validation, packaging, or installation. It only makes invalid persisted validation evidence visible and fail-closed. The application does not write to the live Rocksmith installation or NoCableLauncher.
