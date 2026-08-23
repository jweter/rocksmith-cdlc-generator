# Multi-Source Score Reconciliation and Reference Verification

## Status

Future capability design. This document records an explicitly desired product direction; it does **not** displace the active Product Reality / desktop-authoring milestones in `PROJECT_PLAN.md`.

## Goal

Rocksmith CDLC Generator should eventually be able to accept multiple independent musical-source candidates for the same recording, align each candidate to the song, measure how well each candidate explains the audible performance, rank candidates globally and by section, expose disagreement, and optionally produce a provenance-preserving consensus draft for human review.

The product should not assume that the first Guitar Pro file, tab, chord sheet, or transcription model is authoritative.

The governing question is:

> **Which available evidence best explains what is actually audible in this recording, and where does the evidence disagree enough to require a human?**

This extends the existing confidence/provenance architecture rather than replacing it.

## Candidate-source model

A project may eventually contain multiple registered candidate sources, for example:

- Guitar Pro 3/4/5 files;
- GPX / newer Guitar Pro formats through safe adapters when implemented;
- MusicXML;
- MIDI where its limitations are understood;
- detailed digital tablature;
- ASCII/text tablature;
- chord sheets;
- audio-only transcription candidates;
- manually entered or human-verified reference observations.

Each source remains an independent immutable evidence identity. Reconciliation must never destructively merge or overwrite source provenance.

Example conceptual flow:

```text
                         ORIGINAL RECORDING
                                 |
                      instrument/stem evidence
                                 |
             +-------------------+-------------------+
             |                   |                   |
          GP #1               GP #2               GP #3
             |                   |                   |
             +-------------------+-------------------+
                                 |
                       normalize notation
                                 |
                      align each to recording
                                 |
                    audio <-> source scoring
                                 |
             +-------------------+-------------------+
             |                                       |
       whole-song ranking                       section ranking
             |                                       |
             +-------------------+-------------------+
                                 |
                     disagreement / consensus
                                 |
                           human review
```

## Source capability profiles

Sources must not be treated as if they contain equivalent information.

A structured Guitar Pro or MusicXML score can potentially provide pitch, rhythm, duration, string/fret position, chords, measures, and techniques. A text tab may provide string/fret information with weak timing. A chord sheet may provide only harmonic context and section labels.

The reconciliation engine should therefore register a capability profile per source, such as:

```text
structured score    pitch rhythm duration string/fret chords measures techniques
MIDI                pitch rhythm duration              chords/measures (limited)
detailed tab        pitch? rhythm? string/fret         section labels (variable)
ASCII tab           string/fret, ordering              approximate timing only
chord sheet         chord/harmony + section context    no authoritative voicing
```

Missing information is `unknown`, not evidence that the event is absent.

## Candidate scoring

Candidate ranking should combine multiple independent metrics rather than a single timing score.

Potential dimensions include:

- pitch agreement with isolated/full-mix audio evidence;
- onset agreement;
- duration/sustain agreement;
- chord-tone agreement;
- rhythmic agreement;
- structural/section agreement;
- repeated-riff consistency;
- technique evidence (bend, slide, mute, harmonic, etc.);
- tuning compatibility;
- fretboard/playability plausibility;
- agreement with already human-reviewed timing or event authority.

Scores must retain metric-level detail and uncertainty. A single composite score is useful for ranking but must not hide why one source won.

Example UI result:

```text
Candidate                    Overall
------------------------------------
source-a.gp                  94.2
source-b.gp5                 89.7
source-c.musicxml            82.4

Best intro:                  source-b.gp5
Best verse:                  source-a.gp
Best solo:                   source-c.musicxml
```

## Section-level winners

The system must not require one file to be best for the entire song.

A candidate can be best overall while another is measurably more accurate for an intro, solo, breakdown, or outro. Reconciliation should therefore operate at project, arrangement, section/phrase, and ultimately event-region granularity where justified.

This allows the software to identify a best source per region without silently declaring the entire source authoritative.

## Consensus arrangement

A later stage may construct a consensus candidate from the strongest evidence per region/event.

Consensus is a **derived draft**, never a new source of truth.

Every consensus event should retain:

- source candidate IDs that support it;
- audio-evidence score(s);
- disagreement alternatives;
- combined confidence;
- the rule/model/version that selected it;
- whether human review is required;
- any human acceptance/rejection authority applied afterward.

Example:

```json
{
  "event_id": "consensus-000742",
  "time": 74.512,
  "pitch": 57,
  "string": 3,
  "fret": 7,
  "evidence": {
    "audio": 0.93,
    "gp_candidate_1": 1.0,
    "gp_candidate_2": 1.0,
    "text_tab": 0.80,
    "chord_sheet": 0.60
  },
  "combined_confidence": 0.97,
  "review_required": false
}
```

## Disagreement-first review

The highest-value UI is not just a leaderboard. It is a disagreement navigator.

Example:

```text
02:18.420-02:22.100
Source A: E5 G5 A5
Source B: E5 G5 Bb5
Source C: E5 G5 A5

Audio evidence:
A5 probability:   high
Bb5 probability:  low

Suggested consensus: E5 G5 A5
Confidence: high
Review: optional
```

For ambiguous evidence:

```text
03:14.200-03:16.800
Source A: bend at fret 12
Source B: fret 14 sustained
Source C: slide 12 -> 14
Audio evidence: ambiguous
Confidence: low
Review: required
```

The user should spend time where independent evidence disagrees rather than reviewing every correct event equally.

## Professional printed score books as human reference evidence

A project user may legally own professionally published guitar or bass score books and use them as private reference material during personal authoring.

The product should support this as **human verification evidence**, while preserving the repository's copyright boundary.

Useful workflows include:

1. The user manually checks a disputed section against an owned score book and records a structured verification result (for example: `Source A is correct for measures 47-51`, or `bass note should be C#3 at this onset`).
2. The user supplies a photograph/screenshot of a limited page/section for private review in a tool that can inspect the notation, then records only the resulting verification/decision in the project.
3. A future private/local notation-image reader may propose note/chord observations from user-supplied page images, but those observations remain untrusted until reviewed and must retain provenance to the local reference image identity.

### Copyright and storage boundary

Published score-book pages, scans, photographs, or substantial transcriptions are copyrighted source material unless separately licensed for redistribution.

Therefore:

- do **not** commit score-book images or copied score pages to this Git repository;
- do **not** add commercial score scans to public benchmark fixtures;
- do **not** upload/distribute the score book as part of CDLC output;
- keep private reference images local to the user's project workspace when used;
- retain hashes/metadata/decision provenance where useful without embedding the copyrighted page itself;
- commit only redistributable test fixtures and abstract verification records that do not reproduce protected notation at substantial scale.

The score book can be authoritative **evidence for the human reviewer** without becoming repository content.

## Human-verification authority

A human verification must be explicit and scoped.

Examples:

```text
verified region: 01:32.400-01:38.100
arrangement: bass
reference type: owned printed score
result: candidate B matches reference
reviewer: human
```

or:

```text
verified source events: [evt-1012, evt-1013, evt-1014]
correction: source candidate A note 2 is wrong; accepted pitch = F#3
reference type: owned printed score
```

The application should distinguish:

- machine audio evidence;
- independent digital-score agreement;
- human manual verification;
- human verification assisted by a privately supplied page image.

Human-reviewed authority can outweigh lower-confidence machine evidence, but it must remain bound to the exact recording/source/event identities it reviewed so stale-state rules still work.

## Proposed desktop experience

A mature Song Workspace could expose a `Compare Sources` surface:

```text
COMPARE SOURCES

[x] candidate-a.gp
[x] candidate-b.gp5
[x] candidate-c.musicxml
[x] guitar-tab.txt
[x] chords.txt

[ Analyze & Rank Sources ]
```

Result:

```text
Best overall:       candidate-a.gp       94%
Best intro:         candidate-b.gp5      97%
Best rhythm:        candidate-a.gp       95%
Best solo:          candidate-c.musicxml 92%

Consensus confidence:                    97%
Disagreement regions requiring review:   14
```

Selecting a disagreement should jump directly to synchronized playback, waveform/timeline, candidate event overlays, fretboard/chord view, and any available human reference-verification control.

## Phased implementation

This should be implemented only after the current single-score alignment/review workflow is stable enough to serve as the comparison foundation.

Recommended order:

1. register multiple structured score candidates without changing current authority;
2. normalize all candidates into the canonical arrangement/event model;
3. independently align each candidate to the same recording/shared timing basis;
4. implement deterministic source-to-source comparison;
5. add audio-to-candidate scoring metrics;
6. add whole-song ranking;
7. add section/phrase ranking;
8. add disagreement visualization and navigation;
9. add provenance-preserving consensus draft generation;
10. add structured manual human-verification records;
11. add private reference-image-assisted verification;
12. add text/ASCII tab adapters;
13. add chord-sheet harmonic evidence;
14. evaluate automatic notation-image extraction only if it measurably reduces editing time and can preserve provenance/confidence.

## Acceptance principles

A first useful release of this capability should satisfy all of the following:

- multiple candidates can coexist without overwriting one another;
- candidate identity and provenance are immutable;
- the user can see why a candidate or region ranked higher;
- section-level winners are supported;
- disagreement is surfaced, not averaged away invisibly;
- a consensus chart retains event-level provenance;
- low-confidence/ambiguous regions remain review-required;
- human verification can resolve disputes explicitly;
- private copyrighted reference material never needs to enter the repository;
- existing stale-state, validation, export, and packaging gates still apply.

## Success metric

The primary product metric remains **human editing minutes per finished song minute**.

This capability is successful only if comparing/reconciling multiple sources and using targeted human reference checks reduces correction time or increases final-chart confidence enough to justify its complexity.
