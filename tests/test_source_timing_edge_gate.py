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
from rocksmith_cdlc_generator.source_timing_qualification import qualify_project_score_timing
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


def test_qualification_blocks_periodic_late_binding_even_when_zero_shift_ties(
    tmp_path: Path,
) -> None:
    project = tmp_path / "song"
    source_path = project / "sources" / "bass.json"
    source_path.parent.mkdir(parents=True)
    (project / "analysis").mkdir(parents=True)

    pattern = [40, 43] * 4
    ImportedSource(
        provenance=SourceProvenance(
            source_type="guitarpro",
            source_filename="periodic.gp5",
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
                notes=[
                    _symbolic(12.0 + 2.0 * index, midi)
                    for index, midi in enumerate(pattern)
                ],
            )
        ],
    ).write_json(source_path)

    anchors = [
        AlignmentAnchor(
            source_time_seconds=float(value),
            audio_time_seconds=float(value),
            source_beat_index=value,
            audio_beat_index=value,
            confidence=0.9,
        )
        for value in (0, 10, 20, 30, 39)
    ]
    candidate = SharedTimeline(
        method="beat-grid-piecewise-linear-v4",
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
        anchors=anchors,
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

    audio_pattern = [40, 43] * 5
    write_transcription(
        BassTranscription(
            engine="fixture",
            source_path="fixture.wav",
            sample_rate_hz=44100,
            notes=[
                _audio(8.0 + 2.0 * index, midi)
                for index, midi in enumerate(audio_pattern)
            ],
        ),
        project / "analysis" / "bass_raw.json",
    )

    report = qualify_project_score_timing(project, candidate)

    assert report.status == "review_required"
    assert report.best_shift_seconds == pytest.approx(-4.0, abs=0.051)
    assert "leading-edge" in report.reason
