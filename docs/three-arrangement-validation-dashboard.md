# Three-arrangement validation dashboard

The packaged Song Workspace exposes a dedicated **Validation** tab for Bass, Lead, and Rhythm.

## Purpose

The dashboard answers one normal desktop question without requiring the user to inspect project JSON or switch among separate arrangement artifacts: **which configured arrangements are validated, blocked, waiting for validation, or already backed by current Rocksmith XML?**

The view is composed into the final Song Workspace rather than introducing another feature subclass. This follows the roadmap requirement to keep the growing authoring surface testable and to prefer composition where another inheritance layer is unnecessary.

## States

Each arrangement is summarized as one of:

- `NOT CONFIGURED` — the arrangement is outside the current project scope;
- `VALIDATION NEEDED` — no persisted validation report exists yet;
- `BLOCKED` — persisted validation is invalid/unreadable or reports one or more failures;
- `VALIDATED` — current validation is PASS/WARNING, but current Rocksmith XML is not yet ready;
- `XML READY` — current validation and current Rocksmith XML are both present according to the existing Song Workspace authority checks.

The dashboard shows failure/warning counts and a concrete next-action explanation for every row.

## Authority and safety boundary

This is a read-only projection of `SongWorkspaceSnapshot`. It does **not** run validation, accept warnings, repair invalid reports, promote XML, change Bass/Lead/Rhythm musical content, approve source rights, alter score mappings, accept timing/fingering/technique/tone decisions, stage packages, register PSARCs, or install anything.

All existing human review and validation gates remain authoritative. In particular, a persisted invalid validation report remains fail-closed and cannot be represented as ready.

No commercial/private media, CFSM exports, Ubisoft-derived content, or generated private project data is added to the repository.
