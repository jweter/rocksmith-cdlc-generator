# Product Reality — EOF Guitar Pro Timing Parity

Related: #304, #397, #431, PR #413

## Human evidence

Two different Guitar Pro sources for the representative **For Whom the Bell Tolls** recording produced the same original failure in fresh packaged-product testing: Arrangement Preview placed the early Bass/Lead/Rhythm material at roughly 17.7–17.9 seconds even though the performance begins around 8–9 seconds.

The decisive comparison remains Editor on Fire (EOF): the same Guitar Pro source loaded against the same recording in EOF has the expected timing and notes. This makes the application's score-to-recording timing path, rather than the score file alone, the active defect domain.

## Reference implementation

EOF's Guitar Pro importer is in `Berneer/editor-on-fire/src/gp_import.c`. The root EOF license is a permissive BSD-style license and permits modification/reuse with attribution; repository attribution is recorded in `THIRD_PARTY_NOTICES.md`.

The relevant EOF behavior is not GUI-specific:

1. Imported notes retain their musical position inside measures.
2. Realtime note timestamps are calculated from the **project beat map** plus the note's fractional position within the beat.
3. Synchronization is allowed to place leading score beats before audio time zero.
4. Beats that remain before 0 ms are omitted from the imported in-recording beat map, and later source beat indices are offset accordingly.

This matters because a score can already contain leading empty measures/rests. A separate audio-start translation must not be added again in a way that turns an approximately 8–9 second musical entry into an approximately 17–18 second entry.

## Fix in PR #413

PR #413 versioned alignment semantics to `beat-grid-piecewise-linear-v3` and onset refinement v2. It added EOF-compatible pre-roll handling, repeated one-to-one onset evidence, stronger pitch support, and stale-authority invalidation. That fix materially improved the packaged symptom, but follow-up testing proved the defect was not fully closed.

## Residual Product Reality evidence — #431

Packaged build `c4587fd8` reduced the first-event displacement but still placed all three symbolic arrangements late:

- recording entrance for Bass + Lead + Rhythm: approximately **7.109 s**;
- Bass first projected event: **11.773 s**;
- Lead first projected event: **11.773 s**;
- Rhythm first projected event: **11.773 s**;
- residual displacement: approximately **+4.664 s**.

A second musical fingerprint confirms this is chart-content timing, not merely a `First note` control or drawing-window defect. At approximately **77.756 s**, the recording reaches a distinct Lead transition identified in the printed score by a **B-string fret-8** entry. The playback position is around bar 34 while the corresponding symbolic material appears around bar 36: roughly **two measures late**.

The remaining failure class is therefore a periodic-translation ambiguity. A constant-tempo repeating intro can produce several measure-spaced shift hypotheses with similar repeated onset/pitch support. Refinement v2 can then prefer a later-but-plausible occurrence rather than the earliest correct score edge.

## #431 correction

Alignment semantics advance to `beat-grid-piecewise-linear-v4`, which deliberately makes v3 timing authority stale.

Onset refinement v3 keeps the EOF pre-roll contract and adds **leading-edge disambiguation**:

- the first symbolic event proposes an explicit candidate against the earliest reliable equal-pitch recording onset;
- that edge candidate is retained even when repeating-riff hypotheses fill the normal candidate budget;
- the edge receives authority only when the following short symbolic sequence has repeated equal-pitch onset support, so one early transcription blip cannot move the score;
- a supported leading edge can break a raw repeated-match tie between measure-spaced hypotheses;
- no song-specific seconds, bar count, or Metallica-specific rule is encoded.

Source Timing Qualification also advances to `multi-event-bass-onset-consistency-v2`. It remains diagnostic-only, but now fails closed when a materially earlier leading edge is supported by several early equal-pitch events even if the periodic whole-window scoring would otherwise accept the later translation.

## Regression contract

Automated tests now cover three forms of the observed failure class:

1. **Score pre-roll:** score notes at 17–24 s versus recording events at 8–15 s recover the negative translation even when leading score beats move before recording zero.
2. **Double-counted intro:** source events that belong at 8–15 s cannot remain mapped to 17–24 s.
3. **Periodic-riff ambiguity:** when both the current translation and an earlier measure-spaced translation match a repeating riff, the earlier translation wins only when the first reliable onset edge plus the following short sequence supports it. The qualification gate must also block promotion of the later periodic binding.

## Packaged retest after #431

1. Use a Windows Desktop artifact built after the #431 fix merges.
2. Open the representative project and run **Safe Automatic Steps**. The v4 alignment version intentionally makes the prior timing authority stale so it is rebuilt.
3. Complete the existing human timing review/promotion gate when prompted.
4. Verify Bass, Lead, and Rhythm first musical events against the recording. They should align near the actual ~7.1 s entrance rather than ~11.77 s.
5. At approximately 77.756 s, verify the B-string fret-8 Lead transition is at the current musical measure rather than about two bars later.
6. Recheck later passages for drift and the previously reported silent-gap sustain region.

EOF remains the external behavioral oracle for this failure class: when the same lawful local GP/audio pair is tested in both applications, unexplained timing disagreement is a Product Reality defect until resolved.
