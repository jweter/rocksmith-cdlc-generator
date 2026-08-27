# Leading-rest alignment Product Reality follow-up

Packaged acceptance testing on 2026-08-26 confirmed that PR #432 did **not** fix the representative two-measure-late projection after a full **Run Safe Automatic Steps** rebuild, fresh timing review, and re-promotion.

## Confirmed packaged evidence

- real common Bass/Lead/Rhythm entrance: approximately **7.109 s**;
- regenerated first symbolic events: approximately **11.773 s**;
- residual displacement: approximately **+4.664 s late**;
- at approximately **77.756 s**, the official printed-score Lead fingerprint that begins on the B string at fret 8 is current in the recording while the generated chart still places the matching material about two score bars later.

## New source-structure evidence

The privately owned official printed score begins with two guitar-empty **with Bells** measures before the first playable guitar/bass entrance. At the printed 120 BPM / 4/4 tempo, that written leading-rest span is about four seconds, close to the observed residual displacement.

This sharpens the failure mode: the recording beat detector can begin its usable grid at the first strong instrument entrance while the symbolic score begins earlier with written rests. If source beat 0 is bound directly to that first strong audio beat, the alignment consumes the written leading-rest span and projects every playable source event late.

PR #432's v3 onset-edge logic still required reliable equal-pitch evidence at the first symbolic onset. The real packaged project demonstrates that requirement is too strong: the earliest Bass pitch estimate can be weak even when onset timing and the following sequence strongly identify the correct edge.

## Follow-up design

Alignment v5 adds a narrow leading-rest-aware refinement after the general onset pass:

1. derive the leading-rest span from the first playable symbolic event;
2. consider only earlier onset candidates whose displacement is consistent with that source prefix;
3. validate several following source/audio onsets one-to-one;
4. use pitch as supporting evidence rather than requiring the first pitch to be correct;
5. move only the shared global translation and retain EOF-compatible pre-roll semantics;
6. invalidate downstream timing/arrangement authority after any applied repair;
7. never hard-code artist/title, seconds, bar counts, or a song-specific correction.

The existing Guitar Pro warning that repeat structure is not unfolded remains a separate structural concern and must not be conflated with this confirmed leading-edge timing defect.
