# EOF Rocksmith section validation audit

Issue: #414

## Scope

This audit closes the first reference-tracing step for the parity matrix's **Section validation** row without changing musical structure or silently inventing section labels.

Reference authority inspected: `raynebc/editor-on-fire` at commit `4a724f4b068b4dd11a71a4b688707a0ed35b6563` (current upstream `master` during this audit), especially `bin/manual/functions.htm`'s Rocksmith section/event authoring rules. EOF treats Rocksmith section names as a constrained vocabulary and warns when a manually defined Rocksmith section does not match a valid, case-sensitive section name. EOF also documents that Rocksmith sections need a Rocksmith phrase on the same beat and that only one section per beat is exported.

## Generator finding

`src/rocksmith_cdlc_generator/rocksmith_xml.py::_build_common_song_header()` currently emits exactly one section for every Bass/Lead/Rhythm arrangement:

```xml
<section name="song" number="1" startTime="..." />
```

The literal `song` is not in EOF's documented valid Rocksmith section-name vocabulary. The generator currently has no section-validation boundary that would surface this mismatch before XML/package review.

This is therefore a real EOF-parity **GAP**, not an unverified Product Reality judgment. It is repository-visible deterministic output and can be tested without commercial audio, private scores, Rocksmith installation access, or musical interpretation.

## Why this audit does not auto-fix the label

Replacing `song` with `intro`, `verse`, `riff`, or another valid name would manufacture song structure when no reviewed section authority currently exists. The safe fix is not to guess a label. A follow-up implementation should introduce a validated section model/boundary and require section names to come from explicit reviewed/generated structure under deterministic validation.

## Bounded implementation direction

1. Define the EOF/Rocksmith valid section-name vocabulary in one deterministic validation module, with upstream provenance pinned to the audited EOF commit.
2. Validate section names before Rocksmith XML export; invalid names must fail closed or remain review-required rather than being silently rewritten.
3. Stop `_build_common_song_header()` from inventing the invalid `song` section. Until explicit section authority exists, choose a documented safe export policy rather than fabricating structure.
4. Preserve COUNT/END phrase behavior and phrase/section co-location as separate parity work; this audit does not claim those are complete.
5. Add repository-safe synthetic tests for valid names, invalid/case-mismatched names, duplicate same-beat section handling where modeled, and the generated Bass/Lead/Rhythm export path.
6. Update `docs/eof-subsystem-parity-matrix.md` from `UNASSESSED` to `GAP`/`PARTIAL` only when the implementation or the matrix update is promoted with exact-head GREEN preflight.

## Safety and provenance

No EOF code is copied by this audit. It records behavior only. Any later direct/substantial reuse must continue to follow `THIRD_PARTY_NOTICES.md` and file/subtree license review. No private/commercial source material is required for the follow-up regression suite.
