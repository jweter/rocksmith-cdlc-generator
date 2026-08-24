from __future__ import annotations

from pathlib import Path

import pytest

from rocksmith_cdlc_generator.alignment import AlignmentAnchor, AlignmentRegion, AlignmentReport, map_source_time
from rocksmith_cdlc_generator.alignment_onset_refinement import (
    ALIGNMENT_REFINEMENT_PATH,
    refine_project_alignment_from_bass_onsets,
)
from rocksmith_cdlc_generator.source_import import (
    ImportedSource,
    SourceNoteEvent,
    SourceProvenance,
    SourceTrack,
    SourceTrustClass,
)
from rocksmith_cdlc_generator.transcription import BassTranscription, NoteEvent, write_transcription


def _symbolic_note(start: float, midi: int) -> SourceNoteEvent:
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


def _audio_note(start: float, midi: int) -> NoteEvent:
    return NoteEvent(
        start=start,
        duration=0.25,
        midi=midi,
        confidence=0.95,
        pitch_confidence=0.95,
        timing_confidence=0.95,
        review_required=False,
    )


def test_content_aware_refinement_corrects_repeated_global_late_offset(tmp_path: Path) -> None:
    project = tmp_path / "song"
    (project / "analysis").mkdir(parents=True)
    (project / "sources").mkdir(parents=True)
    source_path = project / "sources" / "bass.json"

    midis = [40, 43, 45, 47, 48, 47, 45, 43]
    symbolic = [_symbolic_note(10.0 + index, midi) for index, midi in enumerate(midis)]
    source = ImportedSource(
        provenance=SourceProvenance(
            source_type="guitarpro",
            source_filename="fixture.gp5",
            source_sha256="a" * 64,
            importer="fixture",
            importer_version="1",
        ),
        beat_times_seconds=[float(index) for index in range(40)],
        tracks=[SourceTrack(source_track_index=2, name="Bass", instrument="bass", notes=symbolic)],
    )
    source.write_json(source_path)

    report = AlignmentReport(
        source_path=str(source_path),
        source_sha256="a" * 64,
        recording_sha256="b" * 64,
        track_index=2,
        audio_beat_start_index=0,
        global_offset_seconds=10.0,
        anchor_stride_beats=8,
        matched_beats=40,
        rms_residual_seconds=0.0,
        median_abs_residual_seconds=0.0,
        max_abs_residual_seconds=0.0,
        confidence=0.8,
        anchors=[
            AlignmentAnchor(
                source_time_seconds=0.0,
                audio_time_seconds=10.0,
                source_beat_index=0,
                audio_beat_index=0,
                confidence=0.8,
            ),
            AlignmentAnchor(
                source_time_seconds=39.0,
                audio_time_seconds=49.0,
                source_beat_index=39,
                audio_beat_index=39,
                confidence=0.8,
            ),
        ],
        regions=[
            AlignmentRegion(
                source_start_seconds=0.0,
                source_end_seconds=39.0,
                audio_start_seconds=10.0,
                audio_end_seconds=49.0,
                rms_residual_seconds=0.0,
                max_abs_residual_seconds=0.0,
                confidence=0.8,
            )
        ],
    )
    report.write_json(project / "analysis" / "alignment.json")

    audio = BassTranscription(
        engine="fixture",
        source_path="fixture.wav",
        sample_rate_hz=44100,
        notes=[_audio_note(10.0 + index, midi) for index, midi in enumerate(midis)],
    )
    write_transcription(audio, project / "analysis" / "bass_raw.json")

    record = refine_project_alignment_from_bass_onsets(project, source_path)

    assert record.applied is True
    assert record.shift_seconds == pytest.approx(-10.0)
    assert record.refined_match_count >= 8
    refined = AlignmentReport.model_validate_json(
        (project / "analysis" / "alignment.json").read_text(encoding="utf-8")
    )
    assert map_source_time(refined, symbolic[0].start_seconds) == pytest.approx(10.0)
    assert (project / ALIGNMENT_REFINEMENT_PATH).is_file()


def test_content_aware_refinement_preserves_alignment_when_audio_evidence_is_weak(tmp_path: Path) -> None:
    project = tmp_path / "song"
    (project / "analysis").mkdir(parents=True)
    (project / "sources").mkdir(parents=True)
    source_path = project / "sources" / "bass.json"
    source = ImportedSource(
        provenance=SourceProvenance(
            source_type="guitarpro",
            source_filename="fixture.gp5",
            source_sha256="a" * 64,
            importer="fixture",
            importer_version="1",
        ),
        beat_times_seconds=[0.0, 1.0, 2.0, 3.0],
        tracks=[SourceTrack(source_track_index=0, name="Bass", instrument="bass", notes=[_symbolic_note(1.0, 40)])],
    )
    source.write_json(source_path)
    report = AlignmentReport(
        source_path=str(source_path),
        source_sha256="a" * 64,
        recording_sha256="b" * 64,
        track_index=0,
        audio_beat_start_index=0,
        global_offset_seconds=1.0,
        anchor_stride_beats=2,
        matched_beats=4,
        rms_residual_seconds=0.0,
        median_abs_residual_seconds=0.0,
        max_abs_residual_seconds=0.0,
        confidence=0.8,
        anchors=[
            AlignmentAnchor(source_time_seconds=0.0, audio_time_seconds=1.0, source_beat_index=0, audio_beat_index=0, confidence=0.8),
            AlignmentAnchor(source_time_seconds=3.0, audio_time_seconds=4.0, source_beat_index=3, audio_beat_index=3, confidence=0.8),
        ],
        regions=[
            AlignmentRegion(
                source_start_seconds=0.0,
                source_end_seconds=3.0,
                audio_start_seconds=1.0,
                audio_end_seconds=4.0,
                rms_residual_seconds=0.0,
                max_abs_residual_seconds=0.0,
                confidence=0.8,
            )
        ],
    )
    report.write_json(project / "analysis" / "alignment.json")
    write_transcription(
        BassTranscription(
            engine="fixture",
            source_path="fixture.wav",
            sample_rate_hz=44100,
            notes=[
                NoteEvent(
                    start=0.2,
                    duration=0.25,
                    midi=40,
                    confidence=0.2,
                    pitch_confidence=0.2,
                    timing_confidence=0.2,
                    review_required=True,
                )
            ],
        ),
        project / "analysis" / "bass_raw.json",
    )

    record = refine_project_alignment_from_bass_onsets(project, source_path)
    assert record.applied is False
    unchanged = AlignmentReport.model_validate_json(
        (project / "analysis" / "alignment.json").read_text(encoding="utf-8")
    )
    assert unchanged.global_offset_seconds == pytest.approx(1.0)
