# ADR-035 — Reference Ranking Does Not Equal Tone Approval

## Status
Accepted

## Decision
Similarity against the local Rocksmith tone-reference library is advisory only. A high similarity score cannot mark a generated tone approved or safe for injection.

Reference ranking may propose candidate Rocksmith chains and useful knob starting points, but final tone selection remains subject to the explicit review artifact introduced by ADR-033.

Official Rocksmith references receive a higher prior authority than community CDLC, but this reflects their value as Rocksmith-specific examples rather than proof that they reproduce the target recording accurately.

Future audio analysis and external rig research may re-rank candidates, but neither may bypass the human approval gate.