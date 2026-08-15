# Desktop tones and tone regions

The packaged desktop workflow exposes **Workspace → Tones & Regions…** as the human authority for package-facing tone labels and timed tone changes for Bass, Lead, and Rhythm.

## Authority boundary

Each arrangement requires one default tone label. Optional tone-change rows use an absolute song time and the label that becomes active at that time. Change times must be strictly increasing within each arrangement. The three-arrangement confirmation is stored project-locally in `metadata/tone_regions.json`.

This authority answers only **which named tone should be active, and when**. It does not approve amplifier/effect component choices, knob values, source research, or live-audition results. Those remain governed by the existing tone catalog, binding, review, and audition workflows. It also does not approve score mappings, notes, timing transforms, fingering, techniques, validation/XML readiness, PSARC readiness, or installation.

## Package-generation safety

Tone labels and tone-change timing affect the eventual Rocksmith package. Any changed confirmation therefore advances the project package-generation token before removing stale DLC Builder and PSARC staging state. Reconfirming byte-for-byte equivalent normalized tone authority is a no-op and does not advance generation.

Unreadable persisted tone-region authority fails closed in the desktop window. The user must re-enter and confirm all three arrangements before that surface reports confirmed authority again.

## Follow-on integration

Rocksmith XML export should consume this confirmed authority when emitting arrangement tone declarations and tone-change events. XML export must not infer or silently replace missing tone-region authority, and it must preserve the separate human-approval requirements of the detailed tone component pipeline.
