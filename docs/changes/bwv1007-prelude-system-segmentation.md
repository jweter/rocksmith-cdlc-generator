# BWV1007 Prelude System Segmentation

This slice advances issue #496 from page preprocessing into the first N2 recognition geometry stage.

## Implemented

- Consume only a verified, hash-bound normalized score derivative.
- Suppress broad phone-photo illumination gradients before geometry analysis.
- Detect horizontal notation+TAB system bands using deterministic local-ink projection.
- Return system regions in page reading order with confidence values.
- Preserve exact source and derivative SHA-256 provenance.
- Surface expected-system-count disagreement and low-confidence geometry as warnings.
- Persist private `*-systems.json` sidecars beside the private normalized derivative.
- Expose `cdlc-score-bundle segment-systems` for local diagnostic use.
- Add non-copyrighted synthetic regression tests.

## Real-source development observation

The algorithm was tuned against the geometry of the privately held BWV1007 Prelude page-2 capture without storing that image or its musical contents in Git. Broad-background subtraction was necessary because a simple darkness threshold incorrectly merged the lower half of the phone photograph due to uneven page illumination.

The output remains **untrusted geometry**. System detection does not assert any note, fret, rhythm, rest, tie, or technique.

## Next step

Within each detected notation+TAB system:

1. identify the standard-notation and TAB sub-bands;
2. find barline candidates that align across both sub-bands;
3. segment the first 4–8 measures;
4. preserve page regions and confidence;
5. then begin TAB fret/string and notation-rhythm recognition.

A vertical-line detector must not treat note stems as barlines. Barline candidates therefore need corroborating geometry across the paired standard/TAB regions and must enter review when ambiguous.
