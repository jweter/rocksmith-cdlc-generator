# Product Reality — EOF Guitar Pro Timing Parity

Related: #304, #397, PR #413

## Human evidence

Two different Guitar Pro sources for the representative **For Whom the Bell Tolls** recording produced the same failure in fresh packaged-product testing: Arrangement Preview placed the early Bass/Lead/Rhythm material at roughly 17.7–17.9 seconds even though the performance begins around 8–9 seconds.

The decisive comparison is Editor on Fire (EOF): the same Guitar Pro source loaded against the same recording in EOF has the expected timing and notes. This makes the application's score-to-recording timing path, rather than the score file alone, the active defect hypothesis.

## Reference implementation

EOF's Guitar Pro importer is in `Berneer/editor-on-fire/src/gp_import.c`. The root EOF license is a permissive BSD-style license and permits modification/reuse with attribution; repository attribution is recorded in `THIRD_PARTY_NOTICES.md`.

The relevant EOF behavior is not GUI-specific:

1. Imported notes retain their musical position inside measures.
2. Realtime note timestamps are calculated from the **project beat map** plus the note's fractional position within the beat.
3. Synchronization is allowed to place leading score beats before audio time zero.
4. Beats that remain before 0 ms are omitted from the imported in-recording beat map, and later source beat indices are offset accordingly.

This matters because a score can already contain leading empty measures/rests. A separate audio-start translation must not be added again in a way that turns an approximately 8–9 second musical entry into an approximately 17–18 second entry.

## Local defect

The existing content-aware refinement could discover a negative global correction from score/audio onset evidence, but `_shift_report()` rejected the correction whenever **any** alignment anchor moved before recording time zero. That differs from EOF's proven handling of pre-roll and can leave an otherwise correct score translation stuck at the later beat-grid candidate.

## Fix in PR #413

Alignment semantics are versioned to `beat-grid-piecewise-linear-v3`, which makes prior v2 alignment authority stale and forces affected projects through alignment again.

Onset refinement v2 now:

- compares repeated one-to-one onset evidence rather than allowing one audio event to satisfy many symbolic events;
- uses reliable pitch agreement as additional evidence without requiring every useful onset to have final trusted pitch classification;
- ranks candidate global translations and requires a material improvement plus a distinct winner;
- permits a valid negative translation to move score-only leading beats before recording zero;
- drops only transformed anchors before zero, requires at least two in-recording anchors, and extrapolates the same linear transform for earlier source positions;
- invalidates promoted shared/reviewed timing and downstream arrangement derivatives after refinement;
- keeps the separate Source Timing Qualification Gate before shared timing promotion as a fail-closed diagnostic boundary.

No song-specific offset is encoded.

## Regression contract

Automated tests cover both forms of the observed failure class:

1. **Score pre-roll:** score notes at 17–24 s versus recording events at 8–15 s must recover a -9 s translation even though early score beats then precede recording time zero.
2. **Double-counted intro:** a score whose events belong at 8–15 s but whose initial candidate maps them to 17–24 s must recover the single correct timeline, so source 8 s maps to recording 8 s rather than 17 s.

The existing Source Timing Qualification tests additionally ensure a strong mismatch is blocked before promotion while sparse evidence does not invent a correction.

## Packaged retest

After PR #413 passes CI and merges:

1. Download the Windows Desktop artifact built from the merged fix.
2. Open the fresh `test 02` representative project (or recreate it if the workflow requests a clean project).
3. Run **Safe Automatic Steps** so the stale v2 alignment is rebuilt under v3.
4. Complete the existing human timing review/promotion step when prompted.
5. In Arrangement Preview, verify Bass, Rhythm, and Lead first musical events against the recording.
6. The known approximately 17.9 s first-event symptom must be gone; expected early performance is around the actual 8–9 s entrance.
7. Recheck the previously reported silent-gap sustain region to ensure interval endpoints inherit the corrected timing transform.

EOF remains the external behavioral oracle for this failure class: when the same lawful local GP/audio pair is tested in both applications, unexplained timing disagreement is a Product Reality defect until resolved.
