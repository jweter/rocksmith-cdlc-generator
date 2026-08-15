# Arrangement Edit History v1

This milestone makes accepted manual arrangement edits reversible without weakening the existing source/review authority model.

## Scope

Song Workspace records accepted edits for:

- individual physical string/fret position;
- whole-chord fingering, which shares the reviewed-position authority;
- event onset/duration timing;
- event techniques;
- reviewed Lead/Rhythm chord identity.

Imported score bytes and score-fanout JSON remain immutable. Undo and redo operate only on derivative human-review authority files beneath `review/`.

## Transaction model

Every accepted edit stores one ordered transaction in `review/arrangement_edit_history.json`. A transaction records:

- edit kind and timestamp;
- registered score SHA-256 and format;
- current score-fanout manifest path and SHA-256;
- shared-timeline path and SHA-256 for timing edits;
- exact UTF-8 contents (or absence) of every affected **current-authority** review file before the edit;
- exact UTF-8 contents (or absence) after the edit.

Undo restores the exact recorded `before` snapshot. Redo restores the exact recorded `after` snapshot. Neither operation reruns inference, recomputes a musical decision, or silently promotes confidence into authority.

A single global cursor gives predictable ordering across edit types. After undo, accepting any new arrangement edit truncates the abandoned redo branch.

When a stale derivative review file is explicitly replaced against current authority, its obsolete bytes are not recorded as valid prior authority. The transaction's logical `before` state is absence, so undo removes the newly accepted current layer instead of resurrecting stale timing, techniques, or chord membership. Physical stale bytes are still captured separately during the write so a failed transaction can restore the disk exactly.

## Fail-closed behavior

Undo/redo is refused when:

- the registered score or score-fanout authority no longer matches the transaction provenance;
- a timing transaction's promoted shared timeline no longer matches;
- a managed review file has changed outside the recorded history state;
- history JSON is malformed or its cursor/snapshots are internally inconsistent.

When a new explicit human edit is accepted after score/fan-out/timing authority has changed, obsolete history is not carried forward into the new authority generation.

## Write safety

Review-file snapshots are restricted to project-relative paths and cannot target the history file itself. Each file replacement uses a temporary sibling followed by `replace`. Multi-file history operations validate all target state first and roll back already-applied files if a later file write fails. If persistence of the updated history cursor fails, the review-layer restoration is rolled back to the physical bytes that existed before the attempted transaction.

This is application-level transactional behavior over project files, not a claim of filesystem-wide ACID or crash-proof multi-file commits. A future persistence layer may strengthen crash recovery if Product Reality testing demonstrates a need.

## Desktop workflow

Song Workspace shows **Undo Accepted Edit** and **Redo Accepted Edit** with the global applied/total transaction count and the next edit kind available in each direction.

The controls only become active for current, provenance-valid history. After an undo/redo the workspace refreshes from restored review authority, so preview overlays and draft-currentness checks see the same state that was restored.

## Authority boundaries

Undo/redo does not accept or alter source rights, Bass/Lead/Rhythm mapping, shared-timeline promotion, note pitch, tone choices, validation decisions, package readiness, the live Rocksmith installation, or NoCableLauncher.

Restoring an older review layer can make generated Lead/Rhythm drafts and downstream artifacts stale through their existing review-layer SHA bindings. History does not bypass those staleness gates or regenerate/package automatically.
