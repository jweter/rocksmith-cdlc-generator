# Score role composition overlap review

Multi-track role composition can expose exact duplicate notes, coincident starts, and sustained cross-track overlaps. Those cases cannot be resolved safely from heuristics alone because the correct musical result may be to keep both events, keep the left source event, or keep the right source event.

`score_role_composition_overlap_review.py` adds a provenance-bound human decision contract over the exact overlap evidence emitted by `score_role_composition_overlap.py`. Each decision records the arrangement role, the complete source-track/event references for the current overlap, and one explicit resolution: `keep_both`, `keep_left`, or `keep_right`.

The contract is intentionally partial. A user may review one overlap while every remaining overlap stays unresolved and visible. Validation fails closed when score provenance changes or when any note identity, timing, duration, pitch, string/fret position, overlap kind, source-track index, or event index no longer matches the current overlap report. Duplicate decisions for one overlap are rejected.

This layer records review authority only. It does not apply the decisions, merge note streams, delete duplicates, infer chords, shorten sustained notes, define section ownership, change fan-out, alter shared timing, accept fingering/technique/tone/source decisions, write Rocksmith XML, package CDLC, modify the live Rocksmith installation, or interact with NoCableLauncher. A later composition step must consume only validated decisions and must continue to fail closed for unresolved overlap evidence.

No commercial audio, tabs, DLC, private CFSM exports, Ubisoft-derived content, PSARC packages, or generated private project data belong in this contract or its tests.
