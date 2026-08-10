# ADR-026: Preserve Guitar Pro physical string order

## Context

The Guitar Pro importer currently normalizes strings by sorting them by open MIDI pitch. That happens to produce the expected low-string-first order for ordinary monotonic tunings such as E standard and Drop D, but it is not a valid definition of physical string identity.

For crossed or re-entrant tunings, pitch order and physical string order can differ. Rocksmith string indices are physical positions, so sorting by pitch can silently attach tablature frets to the wrong Rocksmith string even though each imported MIDI pitch still looks plausible.

Guitar Pro numbers strings from the highest physical string as `1` toward the lowest physical string as the largest string number. The generator's canonical string indices are low-string-first.

## Decision

Normalize Guitar Pro string metadata by **Guitar Pro string number descending**, not by open pitch.

For a six-string guitar:

- GP string `6` becomes canonical/Rocksmith string index `0`;
- GP string `5` becomes canonical/Rocksmith string index `1`;
- ...;
- GP string `1` becomes canonical/Rocksmith string index `5`.

The tuning vector follows the same physical order. Open MIDI pitch remains associated with the original Guitar Pro string number and is used only to calculate note pitch (`open_pitch + fret`).

Do not reorder strings to make tunings monotonic and do not silently repair unusual tunings.

## Regression case

A deliberately crossed tuning such as GP strings:

`1=64, 2=59, 3=55, 4=50, 5=67, 6=40`

must normalize to:

`[40, 67, 50, 55, 59, 64]`

with physical mapping:

`6→0, 5→1, 4→2, 3→3, 2→4, 1→5`.

A pitch-sorted implementation would incorrectly move the high-pitched physical fifth string to the top of the canonical order.

## Consequences

- Standard and common lowered tunings remain unchanged.
- Crossed/re-entrant tunings retain physical string identity.
- Existing fret/string positions from Guitar Pro remain trustworthy inputs to guitar authoring validation.
- The downstream Rocksmith tuning vector may be non-monotonic, which is intentional and reflects the source instrument rather than an inferred correction.
