from __future__ import annotations

from pathlib import Path

import pytest

from rocksmith_cdlc_generator.alignment import AlignmentAnchor, AlignmentRegion, AlignmentReport, map_source_time
from rocksmith_cdlc_generator.alignment_onset_refinement import refine_project_alignment_from_bass_onsets
from rocksmith_cdlc_generator.source_import import (
    ImportedSource,
    SourceNoteEvent,
    SourceProvenance,
    SourceTrack,
    SourceTrustClass,
)
from rocksmith_cdlc_generator.transcription import BassTranscription, NoteEvent, write_transcription


def _symbolic(start: float, midi: int) -> SourceNoteEvent:
    return SourceNoteEvent(
        start_seconds=start,
        duration_seconds=0.25,
        midi=midi,
        note_name="E2",
        string_index=0,
        fret=0,
        import_confidence=1.0,
        trust_class=SourceTrustClass.symbolic_unverified,
        review_required=False,
    )


def _audio(start: float, midi: int, *, exact_pitch: bool) -> NoteEvent:
    return NoteEvent(
        start=start,
        duration=0.25,
        midi=midi if exact_pitch else midi + 12,
        confidence=0.78,
        pitch_confidence=0.70 if exact_pitch else 0.40,
        timing_confidence=0.95,
        review_required=True,
    )


def test_refinement_can_drop_score_only_preroll_anchors_and_recover_recording_entry(tmp_path: Path) -> None:
    project = tmp_path / "song"
    (project / "analysis").mkdir(parents=True)
    (project / "sources").mkdir(parents=True)
    source_path = project / "sources" / "bass.json"

    midis = [40, 43, 45, 47, 48, 47, 45, 43]
    symbolic = [_symbolic(17.0 + index, midi) for index, midi in enumerate(midis)]
    ImportedSource(
        provenance=SourceProvenance(
            source_type="guitarpro",
            source_filename="fixture.gp5",
            source_sha256="a" * 64,
            importer="fixture",
            importer_version="1",
        ),
        beat_times_seconds=[float(index) for index in range(40)],
        tracks=[SourceTrack(source_track_index=2, name="Bass", instrument="bass", notes=symbolic)],
    ).write_json(source_path)

    report = AlignmentReport(
        source_path=str(source_path),
        source_sha256="a" * 64,
        recording_sha256="b" * 64,
        track_index=2,
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
    )
    report.write_json(project / "analysis" / "alignment.json")

    audio_notes = [
        _audio(8.0 + index, midi, exact_pitch=index in {1, 6})
        for index, midi in enumerate(midis)
    ]
    write_transcription(
        BassTranscription(
            engine="fixture",
            source_path="fixture.wav",
            sample_rate_hz=44100,
            notes=audio_notes,
        ),
        project / "analysis" / "bass_raw.json",
    )

    record = refine_project_alignment_from_bass_onsets(project, source_path)

    assert record.applied is True
    assert record.algorithm_version == 2
    assert record.shift_seconds == pytest.approx(-9.0)

    refined = AlignmentReport.model_validate_json(
        (project / "analysis" / "alignment.json").read_text(encoding="utf-8")
    )
    assert all(anchor.audio_time_seconds >= 0.0 for anchor in refined.anchors)
    assert refined.anchors[0].source_time_seconds == pytest.approx(10.0)
    assert refined.anchors[0].audio_time_seconds == pytest.approx(1.0)
    assert map_source_time(refined, 17.0) == pytest.approx(8.0)
