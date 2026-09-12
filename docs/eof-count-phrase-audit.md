# EOF COUNT/END phrase export audit

Issue: #414

## Scope

This audit closes the reference-tracing step for the parity matrix's **COUNT phrase / leading count measure** row without inventing musical structure or authoring behavior.

Reference authority inspected: `raynebc/editor-on-fire` at commit `4a724f4b068b4dd11a71a4b688707a0ed35b6563` (current upstream `master` during this audit; the same commit already cited by the "Section validation"-adjacent audit for this generator and by several other closed rows in `docs/eof-subsystem-parity-matrix.md`), specifically `src/rs.c::eof_rs_export_common()` and `src/event.c::eof_song_lookup_first_event()`/`eof_song_add_text_event()`.

## Reference finding

`eof_rs_export_common()` (`src/rs.c:6116` onward) enforces two structural Rocksmith phrase invariants at export time, independent of whatever phrases the user actually authored in the chart:

1. **COUNT phrase at the first beat** (`src/rs.c:6142-6151`): before writing phrase/section XML, EOF calls `eof_song_contains_event(sp, "COUNT", track, EOF_EVENT_FLAG_RS_PHRASE, 2)`. The trailing `2` (`track_specific`) argument, per `eof_song_lookup_first_event()` (`src/event.c:202-229`), matches an event assigned either to the track being exported or to track `0` (EOF's own "applies to every track" convention) -- i.e. "does a COUNT phrase already exist that covers this arrangement." If no such text event exists, EOF logs `"! Adding missing COUNT phrase"` and calls `eof_song_add_text_event(sp, 0, "COUNT", 0, EOF_EVENT_FLAG_RS_PHRASE, 1)`, inserting a project-wide (`track` argument `0`), case-sensitive, all-uppercase `"COUNT"` phrase at beat 0 (position `0`). The trailing `1` (`is_temporary`) means this is injected only for the current export pass and is never persisted back into the user's `.eof` project.
2. **END phrase at the beat after the last note** (`src/rs.c:6178-6193`): the same function separately walks all beats for a manually defined `"END"` RS phrase; if none is found, it logs `"! Adding missing END phrase"` and adds a temporary `"END"` phrase at `endbeat` (the first beat at/after the exported track's last note ends, computed at `src/rs.c:6132-6140`).

Both insertions are unconditional per-export fallbacks, not optional editor conveniences: EOF only warns (and does not skip the insertion) when a conflicting phrase already occupies the target beat. `COUNT` and `END` are fixed, case-sensitive literal names -- unlike the "Section validation" audit's arbitrary musical section vocabulary (`intro`/`verse`/`riff`/etc.), choosing them requires no musical interpretation or reviewed authority.

## Generator finding

`src/rocksmith_cdlc_generator/rocksmith_xml.py::_build_common_song_header()` (the single shared header builder used by all of Bass, Lead, and Rhythm export) currently writes exactly one `<phrase>`/`<phraseIteration>` pair for the entire arrangement:

```xml
<phrases count="1">
  <phrase name="song" maxDifficulty="0" />
</phrases>
<phraseIterations count="1">
  <phraseIteration time="..." phraseId="0" />
</phraseIterations>
```

There is no `COUNT` phrase at the first beat, no `END` phrase at the end of the track, and the single phrase present is named the placeholder literal `"song"`, which is not one of EOF's recognized/auto-managed phrase names. This is therefore a real EOF-parity **GAP**, not an unverified Product Reality judgment: it is deterministic, repository-visible XML output, verifiable without commercial audio, private scores, Rocksmith installation access, or musical interpretation.

## Why this audit does not implement the fix directly

A correct fix touches the same `_build_common_song_header()` function and the same `<phrases>`/`<phraseIterations>` export surface that PR #606's still-open "Section validation" audit (`docs/eof-section-validation-audit.md`) has already flagged as needing a deliberate section/phrase-authority redesign (its placeholder `<section name="song">` is the sibling gap to this placeholder `<phrase name="song">`, and that PR's own review is still deciding the safe export policy for that function). Landing an independent code change to the same function in parallel risks conflicting with that pending redesign. This audit records the traced reference behavior and a bounded follow-up instead, so both gaps can be fixed together (or in a clearly sequenced order) once #606 lands.

## Bounded implementation direction

1. In the same pass (or immediately after) the "Section validation" gap is fixed, extend `_build_common_song_header()` (or its section/phrase-authority successor) to always emit a `COUNT` phrase at the first beat and an `END` phrase at the beat following the arrangement's last note, matching EOF's unconditional fallback -- this requires no reviewed musical authority, since the names and placement are fixed by the Rocksmith/EOF export contract, not by song content.
2. Preserve (or replace, if the section-validation follow-up removes it) the existing single whole-song phrase as a separate, additional phrase distinct from `COUNT`/`END`, mirroring EOF's model where `COUNT`/`END` are structural bookends around whatever real arrangement phrases exist.
3. Add repository-safe synthetic regression tests asserting: a `COUNT` phrase/phraseIteration exists at time `0`, an `END` phrase/phraseIteration exists at the correct end-of-track beat time, and both survive for Bass, Lead, and Rhythm export.
4. Update `docs/eof-subsystem-parity-matrix.md`'s "COUNT phrase / leading count measure" row from `GAP` to `PARITY`/`PARTIAL` only when the implementation lands with exact-head GREEN preflight.

## Safety and provenance

No EOF code is copied by this audit; only the traced control-flow and literal string constants are recorded, with upstream commit/path provenance. No private/commercial source material is required for the follow-up regression suite.
