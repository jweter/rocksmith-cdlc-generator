# Bass separated-stem clone rejection (reconciliation v5)

## Root cause and correction

A valid `stems/bass.json` hash receipt and perfectly aligned content clock
prove **identity and timing**. They do not prove the Bass stem differs from
the original mix. An identical full-mix copy, including one with only
volume adjustment or polarity inversion, could previously pass those gates
and allow high-confidence transcription to promote score authority.

Reconciliation v5 adds `screen_stem_nontrivial_difference` as another
**necessary but NOT sufficient** trust condition.

It reads up to 12 short, disjoint and bounded PCM windows and checks whether
the signal contains nonproportional sample content beyond what could be
explained by a gain/DC or global polarity transform. At least two
signal-bearing windows must establish a substantial difference. Exact
byte-identical files, gain-only copies, phase-inverted copies, silence,
truncated PCM or insufficient material fail closed.

The result is one of:
- `nontrivial_difference` — there is measurable independent signal change;
- `indistinguishable` — an exact/scaled full-mix clone cannot be excluded;
- `ambiguous` — insufficient independent evidence;
- `incompatible` — invalid/mismatched PCM.

**A nontrivial difference is not proof of source-separation purity.**
A changed full mix with arbitrary noise could also pass this screen.
Existing source/digest, model/provenance, pitch confidence and onset/timing
qualification remain required; independent isolation-purity benchmarks and
licensed real-song truth tests remain outstanding.

The algorithm checks no song identity, model licensing, or real gameplay.
It changes no source WAV, note map, beat grid or Rocksmith package.
Previously generated v4 reconciled charts are stale and re-evaluated
under v5 before using note trust.

## Automated negative cases

The regression suite includes identical full mix with a valid receipt and
aligned clock, gain-only adjustment, polarity inversion, weak drums mixed
with clean Bass, silent audio, shortened/truncated PCM and stale v4 artifacts.
All fixtures are original synthesized audio, not uploaded private music.

This closes a specific **false-source-identity trap** and does not close
issue #787 or the broader #796 evidence program.
