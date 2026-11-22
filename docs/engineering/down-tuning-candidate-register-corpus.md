# Canonical #796 slice 37 — down-tuning candidate-register regression

## Production issue

Instrument-focused register preview, fretboard candidate inventory and actual Rocksmith guitar tuning offsets must honor the **declared per-role source open-string MIDI**. They must never substitute standard tuning when a dropped or alternate open string is present. The old source-position inventory enumerated candidates separately from the focused-audio candidate function, and accepted arbitrary tuning lengths and out-of-bounds physical MIDI values; the listening candidate helper accepted empty/malformed pitch arrays and even boolean/float fret bounds. A malformed imported source could thus yield plausible-looking notes or overlarge fret-space iteration. None of these candidates are independent proof of audio correctness.

## Concrete changes

- New pure-core `tuning_contract.explicit_tuning_is_valid()` owns the already-established six-to-eight-string Lead/Rhythm and four-to-six-string Bass contract. The Song Workspace and raw imported candidate inventory now share a source-domain validator without an **inverse dependency from the source importer to a GUI view-model**. GUI import compatibility remains intact.
- `instrument_audio_focus.candidate_positions()` now rejects absent/empty or invalid MIDI open-string arrays and non-integer/boolean/out-of-range 0..30 fret limits. The position formula remains exactly `fret = note_midi - source_open_string_midi` for each physically feasible string.
- `fretboard_candidate_inventory.build_fretboard_candidate_inventory()` reuses the same tested position enumeration and validates the **source instrument's** explicit role-specific tuning and physical 0..30 fret range. No automatic remapping, fingering authority or source mutation.
- Added original, source-free manually calculated corpus covering six guitar tunings (E standard, Drop D, Eb standard, D standard, DADGAD, Drop C) for **both Lead and Rhythm** plus E/Drop D/Eb/D bass and five-string B-E-A-D-G. It compares **exact expected string/fret positions** across focus, raw inventory, physical source note and guitar Rocksmith semitone offsets. Negative cases include Drop D low D becoming impossible in E standard, inconsistent notes, missing/short/wrong-role tuning, booleans/floats in open strings and illegal fret bounds.
- Imported note origin remains untouched. A source physical coordinate that disagrees with the legal search space is `inconsistent`, never silently corrected or passed.

## EOF reference and parity boundary

Inspected mature upstream `raynebc/editor-on-fire@27efe8a85ec8568caaa3ca34ab2d3ea326236725/src/tuning.h` (default and actual tuning lookups, role/strings, played-note calculation, capo/ignore-tuning context) and `src/tuning.c` (played-note lookup used for chord construction). Our stricter explicit-tuning rule intentionally diverges from EOF's user-selectable ignore-tuning behavior: no missing tuning can establish an authoritative candidate and a source is not promoted by a default. No upstream code copied.

## Verified prior dependency and new readiness safety invariant (ERR-2026-023)

Slice 36 was independently reviewed and merged as PR #817, exact head `ff3a08a781a444b2a76667c8818268b4587282ab`, squash merge `e61082118a434a984635540318a297f827423226`. All seven workflows completed with success, including Python 3.12, Windows 3.12/PSARC, Windows Desktop, Golden, Security, Control Plane, Execution Director, Queue Integrity. Codex review completed without findings or unresolved threads. The separate acceptance-hash-bound receipt is reconciled in `engineering/rocksmith-slice-dependencies.json`; **25 merged checked slices, 37 unchecked**.

Reconciliation revealed a new failure mode: previously `classify_queue` used each PR's independent verified merge directly when considering descendant prerequisites, even if a **different prerequisite receipt** was stale/withdrawn. It now computes the transitive dependency-closed subset before admitting any downstream slice. A checked slice with independent merge but missing prerequisite is explicitly `CHECKED_BUT_PREREQUISITES_UNVERIFIED`. Regression injects missing, head-changed, newer-pending, and wrong-merge evidence for #816 and #817; each blocks the appropriate descendant. The original GitHub merge fact remains separately obtainable through `verified_completion_ids`, but cannot substitute for missing prerequisite authority.

## Scope and nonclaims

This is a deterministic source-register consistency fix and corpus, not actual instrument identification, pitch transcription, physical guitar tuning measurement, independent lead/rhythm source isolation, capo verification, historical two-bar phase correction (#455), real commercial-song source truth, Windows Home network isolation or Rocksmith gameplay. Keep those Product Reality/external owner gates untouched. No model execution, private media, binary package, system-setting change or new approval.

**Acceptance:** 37 remains unchecked until its own complete pre-PR regression, exact-head Python and Windows PSARC/Desktop + Golden/Security/Control/Execution Director/Queue CI, independent review with resolved findings, verified merge and a subsequent receipt reconciliation. The existing draft PR #818 covers future **40/41** onset oracles; do not duplicate or merge it prematurely.
