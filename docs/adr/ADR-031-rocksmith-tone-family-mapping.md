# ADR-031: Research-backed Rocksmith tone-family mapping

## Status
Accepted

## Context

ADR-030 introduced source-ranked web-assisted research for track/album/era gear and effect evidence. That evidence is useful, but a researched historical rig is not automatically a valid Rocksmith tone definition. Rocksmith/DLC Builder uses its own tone-device catalog, identifiers, slots, and parameter schema. Guessing those identifiers would create a false sense of fidelity and could produce invalid package data.

The project therefore needs an intermediate mapping layer between historical/audio evidence and exact DLC Builder tone objects.

## Decision

Introduce a conservative `RocksmithTonePlan` that maps evidence-backed tone hypotheses into Rocksmith-oriented component families:

- clean/crunch/high-gain/fuzz amp family;
- compressor, boost, overdrive, distortion, fuzz;
- wah/filter;
- chorus, flanger, phaser, tremolo, vibrato, rotary;
- delay and reverb;
- octave/pitch, gate, and EQ.

Mapping is arrangement-aware. Evidence explicitly scoped to Lead, Rhythm, or Bass applies only to that role; unscoped evidence may apply to all configured roles.

Effect claims below a configurable support threshold are omitted rather than silently promoted into the signal chain. Every generated tone remains `review_required=true`.

`safe_for_automatic_injection` remains false until a separate catalog-binding layer pins authoritative Rocksmith/DLC Builder device identifiers and parameter definitions.

## Trust boundary

A generated tone plan means: "the research evidence supports these broad signal-chain families."

It does **not** mean:

- the exact historical amp/pedal model is known from the mastered recording;
- a specific Rocksmith device is an exact sonic equivalent;
- exact knob values are known;
- the tone should be injected into `.rs2dlc` without review;
- tone-change timestamps have been detected.

Those require later catalog binding, audio verification, and section/tone-change analysis.

## Consequences

This keeps the project useful immediately while preventing unsupported device IDs or parameter guesses from entering the packaging path. It also gives future audio analysis a stable target: compare detected tone/effect families against the researched plan before selecting exact Rocksmith devices.
