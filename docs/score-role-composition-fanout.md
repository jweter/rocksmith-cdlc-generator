# Score role composition fan-out

Issue #232 requires multiple explicitly selected complete-score tracks to contribute to
one Rocksmith Bass, Lead, or Rhythm arrangement without silently losing or duplicating
musical material. The composition contract, the persisted plan, the cross-track overlap
analysis, and the human overlap-decision contract already exist. This slice adds the
first module that actually consumes validated decisions to build one composed note
stream for a role.

`score_role_composition_fanout.py` merges the notes from every source track selected for
one role into a single deterministic `RoleCompositionResult`, ordered by recording-time
start and then by selection order. Every composed note keeps its exact originating
`source_track_index` and `event_index` so provenance through fan-out remains traceable
back to the specific score track it came from.

## Fail-closed boundary

- Composition re-derives cross-track overlap evidence from the exact current
  `ScoreRoleCompositionPlan` and supplied tracks; it never trusts a possibly-stale
  caller-supplied overlap report.
- Every overlap currently reported for the requested role must already carry an explicit
  human decision recorded against that exact overlap (score identity, note timing,
  pitch, and position all included). Any unresolved overlap blocks composition entirely
  for that role.
- Decisions recorded for a different role never resolve this role's overlaps, and a
  decision plan built against a different registered score fails closed.
- `keep_both` never drops a note. `keep_left`/`keep_right` drop only the exact losing
  note identified by that specific overlap finding. If the same note is the explicit
  loser of any decision, it stays excluded even when a different overlap decision would
  otherwise have kept it — exclusion is conservative and never silently reintroduces
  material a human chose to discard.
- A source track referenced by the current role selection but missing from the supplied
  tracks fails closed instead of composing a partial result.

## What this does not do

This is a pure, read-only merge over already-validated inputs. It does not persist a
composed artifact, change score fan-out, write project files, invent timing/technique/
chord/tone/source decisions, alter the shared score-to-recording timing model, write
Rocksmith XML, package CDLC, modify the live Rocksmith installation, or interact with
NoCableLauncher. Composing a role still requires the existing human-confirmed primary
mapping, persisted composition plan, and fully resolved overlap decisions produced by
the earlier slices; this module adds no new source-track selection or overlap-review
authority.

## Next integration step

`score_role_composition_fanout_review.py` now binds this composed result to a persisted
per-role fan-out artifact and wires project-local staleness/invalidation to the full
selected source-track set rather than one track ID, per issue #232's acceptance
direction. See `docs/score-role-composition-fanout-review.md`.

No commercial audio/DLC, private CFSM exports, Ubisoft-derived content, PSARC packages,
or generated private project data belong in this module or its tests.
