# Third-Party Notices

## Editor on Fire

Rocksmith CDLC Generator uses **Editor on Fire (EOF)** as a reference implementation for mature Guitar Pro and Rocksmith authoring behavior. Portions of this project's timing design are already adapted from EOF behavior, and issue #414 establishes a standing program for additional tested parity/adaptation where useful.

### Primary current upstream

Repository: `raynebc/editor-on-fire`  
Upstream copyright: Copyright (c) 2018, T^3 Software  
Upstream license: BSD-style 3-clause license (`license.txt` in the EOF repository)

The upstream license permits redistribution and use in source and binary forms, with or without modification, provided its copyright notice, conditions and disclaimer are retained and contributor names are not used to endorse or promote derived products without specific prior written permission.

### Historical snapshot used by the first timing parity fix

Repository: `Berneer/editor-on-fire`

PR #413's initial timing investigation inspected the Guitar Pro / Go PlayAlong timing implementation in `src/gp_import.c` and related declarations in `src/gp_import.h` from this historical snapshot. The relevant behavior was the ability to synchronize symbolic beats before audio time zero, omit the pre-zero portion and continue mapping later score content through the project beat map instead of rejecting the valid transform.

New EOF audits should normally begin with the current `raynebc/editor-on-fire` lineage so later fixes are not missed. Historical forks remain useful for provenance and comparison.

### EOF first-synchronization-point timing adaptation

Issue #455 re-audited the current primary upstream at commit
`c0d88eabf7b00b0bd2cac9414df9fa9c6b3e7100`, especially
`src/gp_import.c`.

The v6 Guitar Pro timing path in
`src/rocksmith_cdlc_generator/eof_first_sync_alignment.py` is a clean Python
adaptation of the timing semantics relevant to the Product Reality failure:

- realtime note positions are derived from the project beat map and fractional beat position;
- a synchronization point may occur after the beginning of the score;
- beats preceding that synchronization point are walked backward using the beat duration in effect;
- beats that would remain before recording time zero are omitted rather than causing a valid synchronization to be rejected;
- later score content remains on the retained project beat map without a second independent intro offset.

The Python implementation does not copy EOF's C source verbatim and does not bundle or launch EOF. It records the exact upstream repository, file and commit in its generated evidence artifact. The project's separate audio evidence is used only to identify which recording occurrence corresponds to the complete score's first playable synchronization point; once selected, the beat-map translation follows the EOF-derived pre-zero semantics above.

### Repeat and alternate-ending unfolding adaptation

Issue #414's parity item A re-audited the current primary upstream at commit
`c0d88eabf7b00b0bd2cac9414df9fa9c6b3e7100`, specifically `src/gp_import.c`'s
`eof_unwrap_gp_track()` function.

`src/rocksmith_cdlc_generator/eof_repeat_unfolding.py` is a clean Python adaptation of that
function's repeat-start, end-of-repeat, and alternate-ending decision logic:

- a measure marked as a start of repeat resets the current repeat-pass counter the first time
  it is reached;
- a measure with alternate-ending markers is only realized on the repeat pass(es) its bitmask
  selects, and is otherwise skipped forward to the next measure that closes the alternate
  ending's scope, without being realized;
- reaching an end-of-repeat measure with passes remaining jumps back to the most recent start
  of repeat and advances the pass counter; the repeat count is only decremented when the
  measure being left is not itself the currently active alternate ending.

The Python implementation does not copy EOF's C source verbatim and does not bundle or launch
EOF. It intentionally does not port that same function's separate navigation-symbol branches
(Da Capo / Da Segno / Coda / Fine): EOF resolves those from a `gp->symbols` table it populates
while parsing the raw Guitar Pro binary, and PyGuitarPro's parsed object model (this project's
Guitar Pro import dependency) does not expose an equivalent normalized table, so that slice is
explicitly out of scope rather than approximated. The module also verified, by reading
PyGuitarPro's own GP3/GP5 readers (`repeatClose`/`repeatAlternative` handling in `gp3.py` and
`gp5.py`), that PyGuitarPro already normalizes the on-disk repeat-count off-by-one (GP5) and
alternate-ending bitmask (GP3/GP4/GP5) the same way EOF's own version-dependent branches do, so
no separate per-version branch was needed in the port.

This check is advisory only: it reports whether the generator's currently-unimplemented
repeat/alternate-ending unfolding (written score order) agrees with EOF-derived realized
playback order, and never rewrites canonical chart state.

### Explicit rest boundary integrity adaptation

Issue #414's parity item B re-audited the current primary upstream at commit
`c0d88eabf7b00b0bd2cac9414df9fa9c6b3e7100`, specifically the per-beat rest-type
handling inside `eof_load_gp()` in `src/gp_import.c`: a beat bitmask bit signals
whether the beat is a rest, and a following byte distinguishes an "empty" beat
(no notes authored, no rest symbol written) from a "rest" beat (the score
explicitly notates silence) -- but EOF reads and discards that byte without
branching on it. Either way, EOF's parser never creates a note event for a
beat with no notes, so the actual invariant enforced is structural rather than
a ported algorithm.

`src/rocksmith_cdlc_generator/eof_rest_boundary_check.py` reproduces that same
structural invariant for this project's own Guitar Pro importer: it reads
PyGuitarPro's own `BeatStatus.rest` normalization of the same empty/rest
distinction, computes every explicit rest beat's realtime interval, and
cross-checks it against the note intervals the generator's importer would
extract for the same track, reporting any note sustain that overlaps an
explicit rest.

The Python implementation does not copy EOF's C source and does not bundle or
launch EOF. It does not evaluate EOF's separate short-note/staccato/mute
sustain-truncation preferences later in the same function, which remain
unaudited and out of scope for this slice.

This check is advisory only: it reports whether the generator's directly
imported note intervals respect explicit-rest boundaries, and never rewrites
canonical chart state.

### Exact tie-continuation behavior

The reviewed-authoring tie-folding slice inspected current upstream
`src/gp_import.c` at `98753f56ec655e86bd1d753d4e1e30002a94e151`, including
the multi-string tie-extension correction at
`55b6a01896870454dabef588571386842ad8abe0` and the current
different-string behavior after `52268943ad5731c3a567c1c40d605ee3d8bd98b1`.
The implementation is a narrower clean adaptation rather than copied C source: only
tie-only, exact-adjacency, same-string/fret/pitch continuations fold, and source-event
lineage plus the project's stronger trust/review gates remain authoritative.

### Fork classification note

`xmist001/editor-on-fire-automated` was initially surfaced as a possible automation-oriented fork. A deeper repository audit established that it is a direct fork/snapshot of `raynebc/editor-on-fire`; its `master` head is upstream commit `a6b81a4edad6f5b48bd455e98111b56fc007a49d` from 2026-05-21, and that exact commit exists in the primary repository. The May 2026 GP/timing/COUNT changes first noticed through that repository are therefore upstream EOF work, not proven fork-specific automation features.

The repository name alone must not be treated as evidence of a separate automated implementation. It remains a historical snapshot unless unique divergence is later demonstrated.

### Reuse policy

This project's Python implementation is not a bundled copy of the EOF application. Relevant deterministic authoring behavior may be studied, ported, adapted or directly reused when the file-level licensing permits it and doing so is preferable to independently reimplementing mature behavior.

For substantial direct adaptations, record the upstream repository/path and preferably the source commit/SHA in the implementation PR or source documentation. Preserve required BSD attribution and conditions.

The standing audit/reuse plan is documented in:

- `docs/eof-reference-parity-program.md`
- `docs/eof-subsystem-parity-matrix.md`
- `docs/eof-upstream-fork-inventory.md`
- `docs/eof-automated-comparison.md`

Before directly reusing code from any third-party subtree bundled inside EOF, review that subtree's own license separately. This notice applies to EOF project code under its root license; it does not automatically cover every vendored dependency.

## Rocksmith Custom Song Toolkit and adjacent tools

`rscustom/rocksmith-custom-song-toolkit` and relevant forks are reference sources for Rocksmith XML, SNG, package and dynamic-difficulty behavior under issue #414.

Their code is **not** covered by EOF's BSD license merely because it participates in the same authoring ecosystem. Inspect the applicable project/file licenses before any direct code reuse. Until that audit is complete, treat toolkit/DDC source as behavior/design reference material rather than an automatically reusable donor codebase.
