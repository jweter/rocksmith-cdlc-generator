# Product Reality — EOF Guitar Pro Timing Parity

Related: #304, #397, #431, #455, PR #413

## Human evidence

Two different Guitar Pro sources for the representative **For Whom the Bell Tolls** recording produced the same original failure in fresh packaged-product testing: Arrangement Preview placed the early Bass/Lead/Rhythm material at roughly 17.7–17.9 seconds even though the performance begins around 8–9 seconds.

The decisive comparison remains Editor on Fire (EOF): the same Guitar Pro source loaded against the same recording in EOF has the expected timing and notes. This makes the application's score-to-recording timing path, rather than the score file alone, the active defect domain.

## Reference implementation

EOF's Guitar Pro importer is in `raynebc/editor-on-fire/src/gp_import.c`. The root EOF license is a permissive BSD-style license and permits modification/reuse with attribution; repository attribution is recorded in `THIRD_PARTY_NOTICES.md`.

The v6 audit pins current upstream commit `c0d88eabf7b00b0bd2cac9414df9fa9c6b3e7100`.

The relevant EOF behavior is not GUI-specific:

1. Imported notes retain their musical position inside measures.
2. Realtime note timestamps are calculated from the **project beat map** plus the note's fractional position within the beat.
3. Synchronization is allowed to place leading score beats before audio time zero.
4. When the first synchronization point occurs after measure 1, preceding beats are positioned backward using the beat duration/time signature in effect.
5. Beats that remain before 0 ms are omitted from the imported in-recording beat map, and later source beat indices are offset accordingly.

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

The privately owned official printed score also shows two guitar-empty **with Bells** measures before the first playable guitar/bass entrance.

## v4/v5 heuristic correction attempts

Alignment v4 and v5 kept the EOF pre-roll contract but continued to decide the recording translation using project-specific heuristic layers:

- periodic global shift candidate buckets from Bass onset/pitch evidence;
- an explicit earliest equal-pitch edge candidate;
- a leading-rest-distance prior derived from the first playable symbolic event;
- ranking/margin thresholds intended to disambiguate repeated riffs.

Those changes were generic and regression-tested, but they were still our own alignment-selection machinery rather than EOF's first-synchronization-point model.

A separate planner defect then prevented stale alignments from re-running those newer algorithms. PR #451 fixed that staleness bug so `align-tab` actually re-executes when refinement authority changes.

## Packaged retest after #451 — v5 disproven

Fresh packaged Windows testing on **2026-08-28** reran the current path after the planner staleness fix. The representative project still displayed the same residual timing failure: the symbolic arrangements remained late instead of matching EOF.

This removes the prior uncertainty about whether v5 merely failed to execute. The v5 heuristic itself is insufficient on the real project.

That result changes the engineering direction: do not add another song-alignment ranking knob first. The mature implementation already produces the desired result for the same lawful local GP/audio pair.

## v6 direct EOF-derived first-sync path — #455

Alignment authority advances to `beat-grid-piecewise-linear-v6`, intentionally making v5 stale.

For **Guitar Pro** sources with Bass audio timing evidence, v6 no longer runs the old periodic global-shift and leading-rest-distance refinement algorithms. Instead it uses `eof_first_sync_alignment.py`:

1. take the selected symbolic Bass track's **first playable event** as the score-side first synchronization point;
2. compare the short following symbolic onset sequence against the recording using relative timing from the current project beat transform;
3. choose the **earliest strongly supported recording occurrence** of that complete-score prefix, so a later repeated riff cannot win merely because it is closer to the current wrong transform;
4. use timing evidence only for that identification, so one weak/wrong first Bass pitch estimate cannot hide the correct edge;
5. translate the shared beat transform once from that synchronization point;
6. preserve EOF's pre-zero behavior by omitting only anchors/regions that remain before recording zero;
7. if no strongly supported first-sync sequence exists, fail closed rather than falling back to the retired Guitar Pro periodic-shift heuristics.

The generated `analysis/eof_first_sync_alignment.json` records the exact EOF upstream repository, file and commit used as the behavioral reference.

The existing workflow planner still recognizes the v5 refinement evidence filenames. Until that planner contract is migrated in a separate cleanup, a successful/no-op v6 EOF decision writes explicit **non-applied compatibility completion markers** to those legacy files. Their reason text states that the heuristic was not executed; the actual timing authority remains the EOF first-sync artifact. If first-sync evidence is insufficient, those markers are intentionally absent so reconciliation stays blocked.

## Regression contract

Automated coverage for #455 includes the exact residual failure shape without commercial song material:

- first playable symbolic event is currently projected to **11.773 s**;
- a complete matching onset sequence exists at **7.109 s**;
- an equally plausible repeated sequence exists at **11.773 s**;
- the first early pitch estimate is deliberately wrong/weak;
- v6 must select the earlier supported first synchronization point and apply approximately **-4.664 s**;
- the mapped first event must land at **7.109 s**;
- when no sufficiently supported prefix exists, v6 must not invent a correction or emit planner-completion markers.

## Packaged acceptance gate for #455

1. Build a Windows Desktop artifact containing v6.
2. Open the representative project and run **Safe Automatic Steps**. The v6 method version must invalidate the prior v5 alignment and rerun Guitar Pro timing.
3. Review/promote shared timing through the normal human gate.
4. Verify Bass, Lead, and Rhythm first musical events against the recording. They must align near the actual **~7.109 s** entrance rather than **~11.773 s**.
5. At approximately **77.756 s**, verify the B-string fret-8 Lead transition is at the current musical measure rather than about two bars later.
6. Verify later passages remain synchronized with no cumulative drift.
7. If the result still disagrees with EOF, keep #431/#455 open and treat the mismatch as a Product Reality defect; do not compensate with a song-specific offset.

EOF remains the external behavioral oracle for this failure class: when the same lawful local GP/audio pair is tested in both applications, unexplained timing disagreement is a Product Reality defect until resolved.
