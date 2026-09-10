from __future__ import annotations

from pathlib import Path
from statistics import median
from math import sqrt

from .alignment import AlignmentAnchor, AlignmentRegion, AlignmentReport, _source_beats, map_source_time
from .beats import read_tempo_map
from .eof_beat_phase_alignment import (
    map_symbolic_beat_to_audio_time,
    solve_beat_phase,
    symbolic_beat_position_from_source_time,
)
from .source_import import ImportedSource
from .transcription import NoteEvent, read_transcription


_PREFIX_ONSET_LIMIT = 12
_AUDIO_DEDUP_SECONDS = 0.025
_MATCH_TOLERANCE_SECONDS = 0.20


def _timing_usable_audio_notes(notes: list[NoteEvent]) -> list[NoteEvent]:
    return sorted(
        (
            note
            for note in notes
            if note.confidence >= 0.55 and note.timing_confidence >= 0.70
        ),
        key=lambda item: item.start,
    )


def _deduplicated(values: list[float], *, tolerance: float) -> list[float]:
    result: list[float] = []
    for value in sorted(values):
        if not result or value - result[-1] > tolerance:
            result.append(value)
    return result


def _selected_track(source: ImportedSource, track_index: int):
    track = next((item for item in source.tracks if item.source_track_index == track_index), None)
    if track is None:
        raise ValueError(f"alignment track index {track_index} not found in source")
    if not track.notes:
        raise ValueError("alignment track has no symbolic notes")
    return track


def _phase_aligned_report(
    baseline: AlignmentReport,
    source: ImportedSource,
    *,
    source_path: Path,
    audio_beat_start_index: int,
    phase_match_fraction: float,
    phase_mean_error_seconds: float,
) -> AlignmentReport:
    """Rebuild timing so every authoritative audio click is an alignment anchor."""

    tempo_map = read_tempo_map(source_path.parent.parent / ".." / "analysis" / "tempo_map.json")
    source_beats = _source_beats(source, baseline.track_index)
    matched = min(len(source_beats), len(tempo_map.beats) - audio_beat_start_index)
    if matched < 4:
        raise ValueError("fewer than four beats overlap after the solved beat phase")

    source_beats = source_beats[:matched]
    audio_beats = tempo_map.beats[audio_beat_start_index : audio_beat_start_index + matched]
    anchors = [
        AlignmentAnchor(
            source_time_seconds=source_beats[index],
            audio_time_seconds=audio_beats[index].time,
            source_beat_index=index,
            audio_beat_index=audio_beat_start_index + index,
            confidence=audio_beats[index].confidence,
        )
        for index in range(matched)
    ]

    residuals = [audio_beats[index].time - map_source_time(
        AlignmentReport(
            source_path=str(source_path),
            source_sha256=baseline.source_sha256,
            recording_sha256=baseline.recording_sha256,
            track_index=baseline.track_index,
            audio_beat_start_index=audio_beat_start_index,
            global_offset_seconds=audio_beats[0].time - source_beats[0],
            anchor_stride_beats=1,
            matched_beats=matched,
            rms_residual_seconds=0.0,
            median_abs_residual_seconds=0.0,
            max_abs_residual_seconds=0.0,
            confidence=1.0,
            anchors=anchors,
            regions=[],
        ),
        source_beats[index],
    ) for index in range(matched)]
    abs_residuals = [abs(value) for value in residuals]
    rms = sqrt(sum(value * value for value in residuals) / len(residuals))
    med = median(abs_residuals)
    maximum = max(abs_residuals)

    regions = [
        AlignmentRegion(
            source_start_seconds=source_beats[index],
            source_end_seconds=source_beats[index + 1],
            audio_start_seconds=audio_beats[index].time,
            audio_end_seconds=audio_beats[index + 1].time,
            rms_residual_seconds=0.0,
            max_abs_residual_seconds=0.0,
            confidence=min(audio_beats[index].confidence, audio_beats[index + 1].confidence),
        )
        for index in range(matched - 1)
    ]

    mean_beat_confidence = sum(beat.confidence for beat in audio_beats) / matched
    error_factor = max(0.0, 1.0 - phase_mean_error_seconds / _MATCH_TOLERANCE_SECONDS)
    confidence = max(
        0.0,
        min(1.0, mean_beat_confidence * phase_match_fraction * error_factor),
    )
    warnings = [
        warning
        for warning in baseline.warnings
        if "audio start-beat selection" not in warning.lower()
    ]
    warnings.append(
        "Guitar Pro timing rebuilt from an onset-supported audio beat-index phase; every "
        "audio click is an alignment anchor and GP absolute seconds are not recording-time authority."
    )
    if confidence < 0.60:
        warnings.append("Beat-phase alignment confidence is below 0.60; keep timing review-required.")

    return baseline.model_copy(
        update={
            "source_path": str(source_path.resolve()),
            "audio_beat_start_index": audio_beat_start_index,
            "global_offset_seconds": audio_beats[0].time - source_beats[0],
            "anchor_stride_beats": 1,
            "matched_beats": matched,
            "rms_residual_seconds": rms,
            "median_abs_residual_seconds": med,
            "max_abs_residual_seconds": maximum,
            "confidence": confidence,
            "anchors": anchors,
            "regions": regions,
            "warnings": warnings,
        }
    )


def refine_project_alignment_from_beat_phase(
    project_dir: Path,
    source_path: Path,
) -> None:
    """Replace GP seconds-shift refinement with symbolic-beat -> audio-beat phase authority."""

    project = project_dir.expanduser().resolve()
    source_path = source_path.expanduser().resolve()
    alignment_path = project / "analysis" / "alignment.json"
    tempo_path = project / "analysis" / "tempo_map.json"
    transcription_path = project / "analysis" / "bass_raw.json"
    if not alignment_path.is_file():
        raise FileNotFoundError(alignment_path)
    if not tempo_path.is_file():
        raise FileNotFoundError(tempo_path)
    if not transcription_path.is_file():
        raise FileNotFoundError(transcription_path)

    source = ImportedSource.read_json(source_path)
    baseline = AlignmentReport.model_validate_json(alignment_path.read_text(encoding="utf-8"))
    source_beats = _source_beats(source, baseline.track_index)
    track = _selected_track(source, baseline.track_index)
    source_onsets = _deduplicated(
        [note.start_seconds for note in track.notes],
        tolerance=1e-6,
    )[:_PREFIX_ONSET_LIMIT]
    symbolic_onsets = [
        symbolic_beat_position_from_source_time(source_beats, onset)
        for onset in source_onsets
    ]

    audio = read_transcription(transcription_path)
    audio_onsets = _deduplicated(
        [note.start for note in _timing_usable_audio_notes(audio.notes)],
        tolerance=_AUDIO_DEDUP_SECONDS,
    )
    tempo_map = read_tempo_map(tempo_path)
    solution = solve_beat_phase(
        tempo_map,
        symbolic_onset_positions=symbolic_onsets,
        audio_onsets_seconds=audio_onsets,
        tolerance_seconds=_MATCH_TOLERANCE_SECONDS,
    )

    refined = _phase_aligned_report(
        baseline,
        source,
        source_path=source_path,
        audio_beat_start_index=solution.audio_beat_start_index,
        phase_match_fraction=solution.matched_onsets / solution.total_onsets,
        phase_mean_error_seconds=solution.mean_abs_error_seconds,
    )
    refined.write_json(alignment_path)

    # Preserve existing planner/evidence compatibility while changing the timing authority.
    from .eof_first_sync_alignment import (
        EOF_FIRST_SYNC_PATH,
        EOFFirstSyncAlignment,
        _invalidate_downstream,
        _write_planner_completion_markers,
    )

    source_first = source_onsets[0]
    baseline_first = map_source_time(baseline, source_first)
    matched_first = map_symbolic_beat_to_audio_time(
        tempo_map,
        audio_beat_start_index=solution.audio_beat_start_index,
        symbolic_beat_position=symbolic_onsets[0],
    )
    compatibility_shift = matched_first - baseline_first
    record = EOFFirstSyncAlignment(
        source_sha256=baseline.source_sha256,
        track_index=baseline.track_index,
        source_first_playable_seconds=source_first,
        baseline_first_playable_seconds=baseline_first,
        matched_first_playable_seconds=matched_first,
        shift_seconds=compatibility_shift,
        prefix_onset_count=len(source_onsets),
        matched_onset_count=solution.matched_onsets,
        candidate_count=solution.candidate_count,
        applied=abs(compatibility_shift) >= 0.20,
        reason=(
            "Timing authority rebuilt from symbolic GP beat coordinates onto the authoritative "
            f"audio click lattice at beat index {solution.audio_beat_start_index}; "
            f"compatibility delta versus the superseded baseline was {compatibility_shift:+.3f}s. "
            "The delta is evidence only and was not applied as a free-floating seconds offset."
        ),
    )
    record.write_json(project / EOF_FIRST_SYNC_PATH)
    _write_planner_completion_markers(
        project,
        refined,
        source_first_playable_seconds=source_first,
        matched_onset_count=solution.matched_onsets,
    )
    _invalidate_downstream(project)
