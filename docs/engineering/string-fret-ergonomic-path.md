# #796 slice 43 — string/fret ergonomic path

## Scope

`fretboard_ergonomic_path.py` adds `build_ergonomic_fingering_path(inventory)`, a
pure read-model function over the existing `FretboardCandidateInventory` (slice 42's
predecessor, #816 era `fretboard_candidate_inventory.py`). For each imported-source
event it chooses one pitch-correct fretboard position:

- If the source's declared `string_index`/`fret` is already pitch-correct
  (`source_position_status == "candidate"`), that exact position is kept and marked
  `"explicit_score"`. It is never reassigned, however ergonomically favorable an
  alternative candidate looks.
- Every other event (`"missing"` or `"inconsistent"` source position) is resolved
  with a deterministic Viterbi-style shortest-path search over
  `FretboardCandidateInventory`'s own pitch-correct candidate set, minimizing total
  hand travel (summed absolute fret and string distance between consecutive chosen
  positions) across the whole phrase, and marked `"ergonomic_suggestion"`. Ties are
  broken by lowest string index then lowest fret, so the result does not depend on
  dict/set ordering.

## What this is not

This is advisory evidence for a future human-reviewed fingering decision, exactly
like `fretboard_candidate_inventory.py` describes itself as "an evidence/read-model
primitive for future sequence optimization." It does **not**:

- mutate any `SourceNoteEvent` string/fret field,
- feed chart generation, authoring, or export,
- promote a pitch-inconsistent declared position to authority (it is treated the
  same as a missing position and resolved purely from the pitch-correct candidate
  set), or
- claim any real guitarist would choose this exact fingering -- "minimal total fret
  and string distance" is a simple, explainable ergonomic proxy, not a model of
  actual playability, open-position preference, or chord-shape continuity.

## Verification

New targeted tests (`tests/test_fretboard_ergonomic_path.py`, 7 tests) cover: an
explicit valid position is never moved even when cheaper alternatives exist; an
ambiguous event is pulled toward its explicit neighbor; a fully ambiguous phrase
picks the provably minimal-cost path (verified by hand against every reachable
same-string and adjacent-string position); a pitch-inconsistent declared position is
*not* treated as an anchor and the original source note is left unmutated; a single
unconstrained event breaks ties deterministically; and the result round-trips
through JSON.

Full repository suite in this sandbox: 2874 passed, 1 pre-existing failure and 40
pre-existing collection errors, all `ModuleNotFoundError: No module named 'tkinter'`
(this container has no `python3-tk`; confirmed identical on unmodified `main`, so
this is a sandbox limitation, not a regression). `scripts/check_automation_readiness.py`,
`cdlc --help`, `pip check`, `compileall`, and both `git diff --check` forms against
`origin/main` all passed. No model execution, audio, or private media involved.

This slice does not check its own queue checkbox or bind a
`engineering/rocksmith-slice-dependencies.json` receipt; per this repository's
established pattern (see slices 36-41, 44), that reconciliation happens in a later
dedicated PR after independent review and exact-head CI confirm the merge.
