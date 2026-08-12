# ADR-070: Read-only Song Preview click schedule

## Status

Accepted.

## Context

Milestone 11 requires song-plus-click and click-only audition modes whose metronome follows the actual variable-tempo beat map rather than a fixed BPM. The Song Preview snapshot already exposes a trusted canonical beat grid. The next playback-facing contract should preserve that grid exactly and avoid introducing audio-device or editing behavior prematurely.

## Decision

Add a read-only `PreviewClickSchedule` derived only from `SongPreviewSnapshot.beat_times_seconds`.

Each click event retains its full-song beat index and exact canonical timestamp. For diagnostics and future transport rendering, it also exposes the intervals to adjacent beats and a local BPM calculated only from the interval to the next canonical beat. Optional start/end bounds filter which click events are returned without renumbering them or changing surrounding timing.

The builder refuses non-monotonic beat grids and invalid time ranges. It does not infer missing beats, quantize timestamps, classify downbeats, synthesize audio, or mutate the trusted snapshot.

## Boundaries

This layer does not play audio, open audio devices, edit beat timing, create manual anchors, write reviewed timing artifacts, modify imported sources, package DLC, touch the live Rocksmith installation, or interact with NoCableLauncher. Downbeat accent decisions remain separate until measure-phase information is authoritative enough to support them safely.

## Consequences

A future playback engine can schedule click sounds directly from canonical beat timestamps and remain correct for tempo drift and intentional tempo changes. The deterministic schedule can also support timeline diagnostics without conflating playback infrastructure with timing-authority changes.
