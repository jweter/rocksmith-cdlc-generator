from __future__ import annotations

from pathlib import Path

import pytest

from rocksmith_cdlc_generator.alignment import AlignmentAnchor, AlignmentRegion
from rocksmith_cdlc_generator.score_source import ArrangementRole
from rocksmith_cdlc_generator.shared_timeline import SharedTimeline
from rocksmith_cdlc_generator.source_import import (
    ImportedSource,
    SourceNoteEvent,
    SourceProvenance,
    SourceTrack,
    SourceTrustClass,
)
from rocksmith_cdlc_generator.source_timing_qualification import (
    SOURCE_TIMING_QUALIFICATION_PATH,
    qualify_project_score_timing,
)
from rocksmith_cdlc_generator.transcription import BassTranscription, NoteEvent, write_transcription


def _symbolic(start: float, midi: int) -> SourceNoteEvent:
    return SourceNoteEvent(
        start_seconds=start,
        duration_seconds=0.25,
        midi=midi,
        note_name="fixture",
        string_index=0,
        fret=max(0, midi - 40),
        import_confidence=1.0,
        trust_class=SourceTrustClass.symbolic_unverified,
        review_required=False,
    )


def _audio(start: float, midi: int) -> NoteEvent:
    return NoteEvent(
        start=start,
        duration=0.25,
        midi=midi,
        confidence=0.95,
        pitch_confidence=0.95,
        timing_confidence=0.95,
        review_required=False,
    )


def _candidate(project: Path, starts: list[float], midis: list[int]) -> SharedTimeline:
    source_path = project / "sources" / "bass.json"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    ImportedSource(
        provenance=SourceProvenance(
            source_type="guitarpro",
            source_filename="fixture.gp3",
            source_sha256="a" * 64,
            importer="fixture",
            importer_version="1",
        ),
        beat_times_seconds=[float(index) for index in range(40)],
        tracks=[
            SourceTrack(
                source_track_index=2,
                name="Bass",
                instrument="bass",
                notes=[_symbolic(start, midi) for start, midi in zip(starts, midis)],
            )
        ],
    ).write_json(source_path)

    return SharedTimeline(
        method="beat-grid-piecewise-linear-v2",
        recording_sha256="b" * 64,
        score_sha256="a" * 64,
        authority_role=ArrangementRole.bass,
        authority_track_index=2,
        authority_output_json="sources/bass.json",
        authority_output_sha256="c" * 64,
        inherited_roles=[ArrangementRole.bass],
        audio_beat_start_index=0,
        global_offset_seconds=0.0,
        anchor_stride_beats=10,
        matched_beats=40,
        rms_residual_seconds=0.0,
        median_abs_residual_seconds=0.0,
        max_abs_residual_seconds=0.0,
        confidence=0.9,
        anchors=[
            AlignmentAnchor(source_time_seconds=0.0, audio_time_seconds=0.0, source_beat_index=0, audio_beat_index=0, confidence=0.9),
            AlignmentAnchor(source_time_seconds=10.0, audio_time_seconds=10.0, source_beat_index=10, audio_beat_index=10, confidence=0.9),
            AlignmentAnchor(source_time_seconds=20.0, audio_time_seconds=20.0, source_beat_index=20, audio_beat_index=20, confidence=0.9),
            AlignmentAnchor(source_time_seconds=30.0, audio_time_seconds=30.0, source_beat_index=30, audio_beat_index=30, confidence=0.9),
            AlignmentAnchor(source_time_seconds=39.0, audio_time_seconds=39.0, source_beat_index=39, audio_beat_index=39, confidence=0.9),
        ],
        regions=[
            AlignmentRegion(
                source_start_seconds=0.0,
                source_end_seconds=39.0,
                audio_start_seconds=0.0,
                audio_end_seconds=39.0,
                rms_residual_seconds=0.0,
                max_abs_residual_seconds=0.0,
                confidence=0.9,
            )
        ],
        human_confirmed=True,
    )


def _write_audio(project: Path, starts: list[float], midis: list[int]) -> None:
    (project / "analysis").mkdir(parents=True, exist_ok=True)
    write_transcription(
        BassTranscription(
            engine="fixture",
            source_path="fixture.wav",
            sample_rate_hz=44100,
            notes=[_audio(start, midi) for start, midi in zip(starts, midis)],
        ),
        project / "analysis" / "bass_raw.json",
    )


def test_qualification_flags_repeated_nine_second_source_mismatch(tmp_path: Path) -> None:
    project = tmp_path / "song"
    midis = [40, 43, 45, 47, 48, 47, 45, 43]
    candidate = _candidate(project, [17.0 + index for index in range(8)], midis)
    _write_audio(project, [8.0 + index for index in range(8)], midis)

    report = qualify_project_score_timing(project, candidate)

    assert report.status == "review_required"
    assert report.best_shift_seconds == pytest.approx(-9.0, abs=0.051)
    assert report.best_match_count >= 8
    assert report.baseline_match_count == 0
    assert (project / SOURCE_TIMING_QUALIFICATION_PATH).is_file()


def test_qualification_passes_when_score_candidate_already_matches_recording(tmp_path: Path) -> None:
    project = tmp_path / "song"
    midis = [40, 43, 45, 47, 48, 47, 45, 43]
    starts = [8.0 + index for index in range(8)]
    candidate = _candidate(project, starts, midis)
    _write_audio(project, starts, midis)

    report = qualify_project_score_timing(project, candidate)

    assert report.status == "pass"
    assert report.best_shift_seconds == pytest.approx(0.0, abs=0.051)
    assert report.baseline_match_count >= 8


def test_qualification_does_not_turn_one_coincidental_onset_into_a_timing_failure(tmp_path: Path) -> None:
    project = tmp_path / "song"
    candidate = _candidate(project, [17.0], [40])
    _write_audio(project, [8.0], [40])

    report = qualify_project_score_timing(project, candidate)

    assert report.status == "insufficient_evidence"
    assert report.best_shift_seconds == 0.0
