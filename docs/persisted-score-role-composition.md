# Persisted score role composition

Issue #232 requires explicit human-confirmed composition of multiple complete-score tracks into one Rocksmith Bass, Lead, or Rhythm arrangement. The preceding composition contract established the ordered authority model; this slice makes that intent durable inside the project without yet consuming it downstream.

`score_role_composition_review.py` persists the current plan at `review/score_role_composition.json`. Reads and writes share the score-mapping transaction so a mapping confirmation cannot race a composition update. Every read revalidates the registered score bytes, score SHA-256/format, selected track identities, and the current human-confirmed primary mapping for each composed role.

A later mapping change therefore makes the old persisted plan fail closed rather than silently remaining authoritative. The user may explicitly write a new plan after the new primary mapping is confirmed; the new plan is then validated from the current score state before atomically replacing the prior file. Invalid writes do not damage the last valid persisted plan.

This artifact records composition intent only. It does not auto-assign extra tracks, merge note streams, define section scopes, resolve overlaps/conflicts, change score fan-out, alter timing, accept source/fingering/chord/technique/tone decisions, write Rocksmith XML, package CDLC, modify the live Rocksmith installation, or interact with NoCableLauncher. Downstream work must continue to preserve every included source track's provenance and keep overlapping/conflicting material explicit and reviewable.

The persisted review artifact is project-local generated/private state and follows the existing project workspace privacy boundary; no commercial audio/tabs/DLC, private CFSM exports, Ubisoft-derived content, PSARC packages, or generated private project evidence are committed.

## Overlap review and the composed fan-out artifact

`score_role_composition_overlap.py` reports every cross-track overlap (`exact_duplicate`, `coincident_start`, `duration_overlap`) between an exact selected track set's imported notes; it never merges or discards anything. `score_role_composition_overlap_review.py` records explicit human resolutions (`keep_both`, `keep_left`, `keep_right`) against that exact overlap evidence; a resolution that does not match a currently reported overlap is rejected. `score_role_composition_fanout.py`'s `compose_role_notes` fails closed unless every currently reported overlap for a role already carries an explicit decision.

`score_role_composition_fanout_review.py` imports every currently selected source track for a role, composes them via `compose_role_notes`, and persists the result at `review/score_role_composition_fanout.json`. Staleness is bound to the full ordered selected source-track set plus each per-track output's current content, mirroring `source_track_trust_review.py`'s fail-closed/explicit-recompose pattern.

## CLI wiring

`cdlc-score-composition PROJECT COMMAND` plumbs the functions above through to a human-usable command line (`src/rocksmith_cdlc_generator/score_role_composition_cli.py`):

- `plan-show` — print the current persisted composition plan, or `null`.
- `plan-select ROLE TRACK_INDEX [TRACK_INDEX ...]` — set/replace one role's ordered selected tracks (first index must be that role's current human-confirmed primary mapping), preserving every other role's current selection, and print the resulting plan.
- `overlaps ROLE` — import the currently selected tracks for one role and print the exact cross-track overlap evidence (`score_role_composition_overlap.ScoreRoleCompositionOverlapReport`) for human review. Read-only: nothing is persisted and no track output is written.
- `compose ROLE [--decisions FILE]` — import every currently selected source track for the role, merge them per the supplied decisions, and persist the composed fan-out record. `--decisions` points at a JSON file shaped `{"decisions": [...]}` (or a bare JSON list) of `{"role", "overlap", "resolution"}` objects, where each `overlap` is copied verbatim from an `overlaps` result entry and `resolution` is `keep_both`, `keep_left`, or `keep_right`. `score_sha256`/`score_format` are always taken from the live registered score rather than the file, so a decisions file cannot go stale against a score change while still parsing successfully. Omit `--decisions` when the role currently has no reported overlaps. Composition still fails closed with an explicit error naming the unresolved count if any current overlap lacks a matching decision.
- `compose-show` — print the current persisted composed fan-out artifact (`review/score_role_composition_fanout.json`), or `null`.

This CLI wiring adds no new merge/acceptance judgment: every decision is still made by a human and independently revalidated by the existing library functions against the live score/plan/track state. No Song Workspace GUI surface or downstream consumer (reconciliation/authoring/export reading composed multi-track output instead of the single primary-mapped track) is wired yet; those remain open follow-on slices of issue #232.
