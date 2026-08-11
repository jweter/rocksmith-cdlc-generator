# ADR-043: Local tone corpus is recommendation evidence, not an approval authority

## Status

Accepted.

## Context

The private local Rocksmith tone-reference library can now be populated from verified copies of the user's installed PSARC packages and ranked with explainable similarity diagnostics. The next useful step is to expose those references to the tone-authoring workflow.

The corpus contains useful empirical evidence, but source authority and similarity are not sufficient to prove that a retrieved tone is correct for a new arrangement. Repeated or community-authored packages can also duplicate the same chain. Automatically copying a retrieved chain or its knob values into a bound plan would weaken the existing human-review gate.

## Decision

Add a read-only recommendation-evidence adapter between `BoundRocksmithTonePlan` and `ToneReferenceLibrary`.

The adapter:

- queries references only within the same Lead/Rhythm/Bass arrangement role;
- uses resolved Rocksmith device keys from the current bound plan as retrieval evidence;
- requires at least one real device-key overlap before surfacing a candidate;
- preserves source type, package hash/path provenance, score, authority weight, tone fingerprint, descriptors, component slots, device keys, and knob values for reviewer inspection;
- collapses duplicate tone-chain fingerprints so repeated packages cannot crowd out distinct choices;
- refuses unsupported arrangement roles rather than coercing them;
- never mutates the bound tone plan;
- exposes no automatic apply or automatic approval operation;
- marks every result as evidence-only and human-review-required.

A retrieved knob value may therefore be shown to a reviewer but is not copied into the active plan. The existing `tone_review.py` approval workflow remains the only route toward a tone becoming ready for injection.

## Consequences

The local corpus can improve decisions immediately without becoming a hidden authority. Official Rocksmith references can rank ahead of lower-authority sources when evidence is otherwise comparable, while duplicate chains are reduced to one representative candidate.

The immediate follow-up is to add an operator-facing report command and then, after the first real private corpus has been inspected, offer explicit reviewer actions that can propose individual reference-derived component changes without bypassing component/tone approval.

## Safety and rights boundary

This layer reads only normalized private metadata. It does not access or modify the live Rocksmith installation, does not redistribute commercial DLC or extracted Ubisoft content, and does not persist private corpus data in the repository.
