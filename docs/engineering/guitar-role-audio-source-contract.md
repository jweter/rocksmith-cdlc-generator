# Lead and Rhythm audio-source contract — #796 slice 35

## Defect and production boundary

The existing `verified_project_stem(project, role)` in `stems.py` mapped **both** `lead` and `rhythm` to the same generic `stems/guitar.wav` and `stems/guitar.json`. This made the GUI's actual **Stem** audition selector capable of presenting identical source media as separately attributed Lead and Rhythm. A valid SHA-256 receipt for a generic guitar stem establishes recording association, not the intended guitar role.

## Strict per-role provenance (candidate audio, not note authority)

The production resolver now accepts only:
- Bass: `stems/bass.wav` + `stems/bass.json`, existing schema v1 unchanged.
- Lead: `stems/lead.wav` + `stems/lead.json`, schema v2, `instrument=lead`, `stem_role=lead`, `source_kind=role_specific_stem`.
- Rhythm: `stems/rhythm.wav` + `stems/rhythm.json`, schema v2, `instrument=rhythm`, `stem_role=rhythm`, `source_kind=role_specific_stem`.

Every receipt must bind the current private `audio/normalized.wav` SHA-256 through `source_sha256` and the selected stem through `output_sha256`. Wrong role, legacy generic guitar source, stale bytes, a full-mix byte clone, two identically hashed Lead/Rhythm outputs, symlink aliases and missing/malformed receipts fail closed. A future source-separation producer must write these receipts **only after** collecting role-specific provenance; this slice does not introduce or authorize model installation/inference.

**Trust boundary:** Even a valid v2 receipt does *not* independently establish role separation purity, musical note/chord accuracy, tuning, score-to-recording phase, or gameplay. It allows only optional preview playback; transport retains its existing recording-clock geometry validation. Focused EQ remains a non-isolated listening aid. Score-role mapping, chord/technique review and exported arrangement authority do not change.

## Deterministic acceptance

`tests/test_instrument_stem_provenance.py` uses synthetic PCM and no network/model. It checks independent role candidates, missing generic fallback, cross-role tampering, schema v1 and boolean-version rejection, changed recording/stem hashes, original clone and duplicate outputs. The existing Bass v1 stem contract is backward-compatible. Windows/Python, Desktop, pinned PSARC, Golden, security/control and independent review must pass on the exact PR head before issue #796 slice 35 may be checked.

No commercial media, private source paths, unapproved model inference or manual owner gameplay check is involved. The historical two-bar alignment defect (#455), independent Bass-note Product Reality (#787/#612), and genuine role-isolation proof remain open.
