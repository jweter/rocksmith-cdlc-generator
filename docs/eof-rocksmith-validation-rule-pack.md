# EOF-Derived Rocksmith Validation Rule Pack

Tracked by issues #414 and #416.

## Purpose

Editor on Fire (EOF) contains years of accumulated Rocksmith authoring validation knowledge. Rocksmith CDLC Generator already has a stronger automation/provenance/review architecture, but its Rocksmith-specific rule coverage is still incomplete.

This program ports the useful deterministic authoring rules into the generator's existing `ReviewItem` and project-health system rather than copying EOF's legacy GUI.

Primary reference: current `raynebc/editor-on-fire`, especially `bin/rocksmith.panel.txt` and the corresponding Rocksmith/note helper code.

## Product principle

EOF's validation knowledge becomes machine-readable pipeline intelligence:

```text
EOF authoring rule
    -> neutral deterministic validator
    -> ReviewItem / project health
    -> safe automatic correction only when the rule is unambiguous
    -> human review when musical intent is required
```

Do not fabricate musical data merely to clear a warning.

## Rule classes

### Class A — hard Rocksmith constraints

Violations should block packaging when the current project model proves the violation.

Initial examples:

- Rocksmith 2014 playable fret > 24;
- invalid/unexportable physical string/fret mapping;
- future: invalid Rocksmith difficulty range, section/phrase hard limits, malformed technique targets and other proven format constraints.

### Class B — lossless-export gaps

The score contains meaningful information but the current neutral model does not preserve enough detail to export it faithfully. These are warnings until structured support exists.

Initial examples:

- bend presence without preserved strength/curve points;
- slide presence without preserved end fret/direction/link-next detail;
- chord fingering not yet modeled/exported;
- fret-hand-position anchors not yet modeled/exported.

The correct long-term fix is to extend the neutral model and authoring/export pipeline, not to hide the warning.

### Class C — suspicious but potentially intentional authoring

These require author review because the notation can be intentional.

Initial example:

- bend on an open string, matching EOF's authoring warning behavior.

### Class D — structural authoring guidance

Planned after the current model can represent the required concepts:

- COUNT phrase and required empty measure;
- END phrase placement;
- phrase/section counts and ordering;
- tone-change placement;
- dynamic-difficulty presence;
- FHP range/width violations;
- handshape/fingering violations with explicit reasons;
- pitched slides missing target/link-next;
- technique notes without valid target notes;
- unsnapped notes and timing-grid consistency.

## V1 implementation — issue #416

V1 intentionally uses only facts already represented by the current neutral models.

### Implemented rule IDs

| Rule ID | Severity | Applies to | Meaning |
|---|---|---|---|
| `rocksmith_fret_limit_exceeded` | FAIL | Bass/Lead/Rhythm | Playable fret exceeds Rocksmith 2014 fret 24 limit. |
| `rocksmith_open_string_bend` | WARNING | Bass/Lead/Rhythm | Bend occurs on an open string; EOF flags this for author review. |
| `rocksmith_bend_detail_missing` | WARNING | Bass/Lead/Rhythm | Bend exists but strength/curve detail is not represented in the current neutral model. |
| `rocksmith_slide_detail_missing` | WARNING | Bass/Lead/Rhythm | Slide exists but end-fret/direction/link-next detail is not represented. |
| `rocksmith_chord_fingering_missing` | WARNING | Lead/Rhythm | Chords exist but current export writes undefined fingering. |
| `rocksmith_fhp_missing` | WARNING | Lead/Rhythm | Playable guitar events exist but current export has no fret-hand-position anchors. |

Bend and slide receive specialized findings instead of also producing a duplicate generic `unsupported_imported_technique` warning.

### V1 non-goals

- no fabricated bend strengths;
- no fabricated slide targets;
- no automatic fingering generation;
- no automatic FHP generation;
- no COUNT/END generation;
- no dynamic-difficulty changes;
- no package-authority changes;
- no live Rocksmith or NoCableLauncher modification.

## V2 — structured technique fidelity

Extend the neutral source/arrangement model so Guitar Pro information can survive the entire pipeline instead of collapsing to technique labels.

Audit and implement:

- bend strength and bend curve points;
- slide direction/type/end fret/link-next;
- grace/slide-in semantics;
- HOPO direction;
- tremolo intervals;
- harmonic variants;
- staccato and note-gap behavior;
- ties and sustain endpoint rules.

Exit gate: EOF-vs-generator synthetic fixtures can compare the relevant semantic fields, and V1 lossless-detail warnings disappear only when the structured representation is genuinely available.

## V3 — playability intelligence

Port/adapt mature EOF logic for:

- chord fingering inference;
- fingering validation;
- fingerless/muted-note behavior;
- FHP generation;
- FHP range/width rules;
- handshape/arpeggio creation;
- handshape/FHP violation explanations;
- chord-slide handshape transitions.

Desired UX is not EOF's visual shell. Surface the reason and suggested correction in the modern Song Workspace, with provenance and explicit acceptance.

## V4 — song structure and export readiness

Audit and adopt:

- COUNT phrase behavior;
- empty measure after COUNT;
- END phrase placement;
- section vocabulary/count/ordering;
- phrase iteration constraints;
- tone-change placement;
- note/tech-note relationship checks;
- dynamic-difficulty readiness;
- Rocksmith XML semantic validation.

## V5 — deterministic self-repair

Only after parity and structured data exist, classify rules by whether the generator can repair them safely.

Examples that may become safe auto-fixes:

- millisecond endpoint resnapping caused only by floating-point rounding;
- deterministic phrase/event normalization;
- generated FHPs when one unique playability-safe solution exists.

Musical ambiguity continues to route to review.

## UX requirements

The Song Workspace should progressively expose EOF-grade explanations in modern form:

- what is wrong;
- where it occurs;
- why Rocksmith cares;
- whether packaging is blocked;
- whether the source data is missing or contradictory;
- whether a deterministic correction is available;
- what human decision is required otherwise.

Repeated findings should remain grouped by root cause while preserving the full per-event audit trail.

## Testing strategy

Every adopted rule requires:

1. a tiny synthetic positive case;
2. a boundary/false-positive case;
3. a negative case where applicable;
4. integration proof that the rule appears in the existing validation/review artifacts;
5. EOF source/path/commit provenance recorded when substantial implementation behavior is ported;
6. Product Reality observation when the rule affects real authoring workflow.

Commercial song/audio/tab content remains local/private. Commit only synthetic/original/redistributable fixtures or media-free observations.

## Success metrics

Track whether the rule pack reduces:

- silent Rocksmith-invalid output;
- manual EOF cross-checking;
- repeated Product Reality defect discovery;
- corrections per finished arrangement;
- editing minutes per finished minute.

The long-term target is not merely more warnings. It is to convert mature EOF authoring knowledge into deterministic prevention, safe self-repair, and focused human review.
