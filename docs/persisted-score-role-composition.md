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

## Song Workspace status layer

`score_role_composition_workspace_status.py`'s `inspect_score_role_composition_workspace_status` is the first Song Workspace GUI surface slice for #232, following the same read-only-status-first pattern `track_trust_workspace_status.py` established for track source trust. Per role (Bass/Lead/Rhythm) it reports one of:

- `unmapped` — no human-confirmed primary score mapping yet;
- `single_track` — the confirmed primary track is the only currently selected track; the existing single-track fan-out remains authoritative and nothing needs composing;
- `multi_track_pending` — the persisted composition plan currently selects more than one track for the role and no persisted composed fan-out record matches that exact selection yet; the live cross-track overlap count (via `preview_score_role_composition_overlaps`) is reported so a human knows how many overlaps still need explicit decisions before composing;
- `multi_track_composed` — the persisted composed fan-out (`review/score_role_composition_fanout.json`) already matches the current multi-track selection.

A stale/corrupt persisted composition plan or fan-out record is surfaced via `plan_stale_detail`/`fanout_stale_detail` instead of raising, and the affected role(s) fall back to their confirmed-primary-only selection rather than silently keeping stale multi-track authority. This function never records a selection, resolves an overlap, composes a note stream, or mutates project files.

## Song Workspace controller/panel

`score_role_composition_workspace_controls.py` (mirroring `track_trust_workspace_controls.py`) presents the status above as deterministic, widget-ready state per role: a status line, a "Compose From Selected Tracks" button label/enabled flag, and combined blocker text. `compose_role_composition_from_workspace` performs the one action this panel currently exposes — composing a role's currently selected tracks — and only when the role is `multi_track_pending` with zero unresolved cross-track overlaps; a role with unresolved overlaps stays disabled with guidance pointing at the `cdlc-score-composition overlaps`/`compose --decisions` CLI. The underlying compose call still independently reimports every selected track and revalidates rights, mapping, plan, and overlap-decision coverage at write time, so this is user-facing guidance rather than an authority bypass.

`score_role_composition_workspace_ui.py`'s `ScoreRoleCompositionWorkspaceMixin` (mirroring `track_trust_workspace_ui.py`) wires that controller into a Song Workspace panel, keyed off the same arrangement-role selector the track-trust panel already uses, and is included in `AudioOutputSongWorkspaceWindow`'s mixin chain.

## In-workspace track picker

The panel also exposes an "Add track"/"Remove track" picker so `plan-select`-equivalent edits (adding/removing a role's selected score tracks) no longer require the CLI. `ScoreRoleCompositionWorkspaceItem` now reports each mapped role's `available_source_track_indices`/`_names` — every score track not currently in that role's selection — and `_present_item` turns that into `ScoreRoleCompositionWorkspaceControl.available_tracks` (picker-ready `ScoreRoleCompositionTrackOption` label/index pairs) plus `removable_track_indices` (every currently selected track except the confirmed primary, which always occupies index 0 and can never be removed here).

`add_score_composition_track`/`remove_score_composition_track` in `score_role_composition_workspace_controls.py` perform the two new panel actions: each merges the one-role edit into the rest of the persisted plan (preserving every other role's current selection, mirroring the CLI's `plan-select` merge behavior) and delegates the write to `record_score_role_composition`, which independently revalidates the current registered score, that the edited selection still starts with the role's confirmed primary track, and that every index names a known score track. Both precheck against the currently reported available/removable tracks for user-facing guidance, but neither grants any authority beyond that revalidated write — adding a track never composes a note stream or resolves an overlap by itself, and a role may move to `multi_track_pending` and still require the existing zero-overlap "Compose From Selected Tracks" action (or the CLI, for unresolved overlaps) afterward.

## In-workspace overlap-decision UI

The panel now also lets a human resolve a `multi_track_pending` role's unresolved cross-track overlaps and compose it without leaving the Song Workspace. `ScoreRoleCompositionWorkspaceItem.overlaps` (populated only in the `multi_track_pending` state) carries the exact `CompositionOverlap` evidence `preview_score_role_composition_overlaps` currently reports for that role, verbatim; `_present_item` turns each entry into a `ScoreRoleCompositionOverlapOption` (a stable `index`, its `kind`, a human-readable `label`, and the underlying `overlap` payload) on `ScoreRoleCompositionWorkspaceControl.overlaps`.

The panel offers only the same three explicit resolutions the CLI's `compose --decisions` accepts (`OVERLAP_RESOLUTION_CHOICES = ("keep_both", "keep_left", "keep_right")`); nothing infers, defaults, or silently picks one. A human picks one overlap and one resolution at a time and records it locally in the panel; composing is enabled only once every currently reported overlap for that role has an explicit recorded decision, mirroring the CLI's fail-closed "every overlap needs a decision" rule. Clicking compose calls `resolve_score_composition_overlaps_from_workspace` in `score_role_composition_workspace_controls.py`, which builds a `ScoreRoleCompositionOverlapDecisionPlan` from the recorded per-overlap decisions and drives it through the exact same validated write path the CLI's `compose` command uses: `compose_and_persist_score_role_composition_fanout`. That call independently reimports every selected track and revalidates that each decision matches one exact current reported overlap before writing anything, so the panel's prechecks (role state, decision completeness, only-offered resolutions) are user-facing guidance rather than an authority bypass. A reported overlap set change (from an add/remove-track edit, a compose, or any other refresh) invalidates any partially recorded decisions rather than silently reapplying them to different overlap evidence.

`score_role_composition_workspace_ui.py`'s `ScoreRoleCompositionWorkspaceMixin` gained the matching overlap/resolution combobox pair, a "Record Decision" button, a decided-count progress label, and a "Compose With Decisions" button wired to `_record_score_composition_overlap_decision`/`_resolve_score_composition_overlaps`. Resolving overlaps via `cdlc-score-composition overlaps`/`compose --decisions` remains available as an equivalent CLI path.

The downstream consumer that reads `review/score_role_composition_fanout.json` for a role instead of only the single primary-mapped track (touching `shared_guitar.py` and `score_fanout.py`) remains an open, larger, riskier follow-on slice of issue #232, deliberately left for its own dedicated run.
