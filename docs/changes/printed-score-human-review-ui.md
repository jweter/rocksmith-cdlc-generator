# Printed score human review UI

Status: implementation slice

This slice turns locally recognized printed-score candidates into a user-reviewable authority workflow inside the Windows desktop app and then connects approved review output directly to the existing deterministic printed-notation Rocksmith practice builder.

## User workflow

1. Open the private printed-score project in the Windows desktop app.
2. Use **Recognize…** and choose the printed page, local Ollama model, measure count, and expected system count.
3. Recognition runs in the existing background worker so the UI remains responsive.
4. The human review window opens automatically when recognition finishes.
5. Review each measure crop against the proposed note/rest events and warnings.
6. Correct, add, or delete events as needed.
7. Approve each measure.
8. Export the reviewed fixture at the desired practice BPM.
9. Use **Build Practice** to generate the validated Bass Rocksmith XML and paired click-track WAV with count-in.

A standalone `cdlc-score-review` command remains available for development/testing.

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

## Desktop practice build

The **Build Practice** action locates the newest reviewed fixture in the private project and reuses `printed_notation_authoring.import_project_printed_notation_practice()` rather than introducing a second timing/export implementation.

That existing fail-closed pipeline provides:

- canonical printed-notation import;
- user-confirmed authoring authority checks;
- deterministic tempo map;
- configurable count-in;
- click-track WAV;
- Rocksmith Bass XML;
- same-string sustain validation;
- click/measure sample-alignment validation.

The desktop therefore now has a single practical path from photographed score evidence to human-reviewed Rocksmith practice output without a manual fixture handoff.

## Next slice

Run the first real laptop acceptance test against the registered BWV1007 Prelude page 2 with local Ollama, inspect recognition quality measure-by-measure, and fix any real-photo segmentation/vision/review defects before expanding recognition to the rest of the Prelude pages.
