# Printed score human review UI

Status: implementation slice

This slice turns locally recognized printed-score candidates into a user-reviewable authority workflow inside the Windows desktop app.

## User workflow

1. Run local printed-score recognition to create a private `*-candidates.json` file.
2. Open the project in the Windows desktop app.
3. Use **Review Printed Score…**.
4. Review each measure crop against the proposed note/rest events and warnings.
5. Correct, add, or delete events as needed.
6. Approve each measure.
7. Export the reviewed fixture at the desired practice BPM.

A standalone `cdlc-score-review` command is also available for development/testing.

## Review authority

The review record is bound to the exact recognition-candidate SHA-256 and normalized derivative identity. If the candidate file changes after review begins, export is refused and the review must be repeated.

Review state is written atomically under the private project directory. Generated reviewed fixtures are also forced to remain inside the project directory.

An approved/corrected event becomes:

- `human_reviewed=true`;
- `review_required=false`;
- `human_review=1.0` confidence evidence;
- source measure-region provenance preserved.

The original vision confidence is retained separately as evidence and does not become review authority.

## Review UI

For each measure the UI shows:

- the actual private cropped notation/TAB image;
- reading-order note/rest candidates;
- beat and duration;
- string and fret;
- techniques;
- deterministic warnings;
- model ambiguity notes;
- measure review status.

The reviewer can:

- correct a selected event;
- add a missing note/rest;
- delete a false positive;
- mark a measure approved/corrected;
- return a measure to pending;
- save the review transaction;
- export only after every selected measure is reviewed.

Explicit rest/note overlap and events extending beyond the measure remain hard export errors.

## Next slice

Connect the reviewed fixture directly into deterministic printed-notation authoring and practice-audio generation so the Windows workflow can proceed from reviewed Bach measures to count-in/click and a Rocksmith test arrangement without a manual file handoff.
