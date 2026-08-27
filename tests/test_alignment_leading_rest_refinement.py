from __future__ import annotations

from pathlib import Path

import pytest

from rocksmith_cdlc_generator.alignment import (
    AlignmentAnchor,
    AlignmentRegion,
    AlignmentReport,
    map_source_time,
)
from rocksmith_cdlc_generator.alignment_leading_rest_refinement import (
    refine_project_alignment_from_leading_rest,
)
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
        duration_seconds=0.20,
        midi=midi,
        note_name="fixture",
        string_index=0,
        fret=max(0, midi - 40),
        import_confidence=1.0,
        trust_class=SourceTrustClass.symbolic_unverified,
        review_required=False,
    )


def _audio(start: float, midi: int, *, pitch_confidence: float = 0.95) -> NoteEvent:
    return NoteEvent(
        start=start,
        duration=0.20,
        midi=midi,
        confidence=0.95,
        pitch_confidence=pitch_confidence,
        timing_confidence=0.95,
        review_required=False,
    )


def test_leading_rest_uses_onset_sequence_when_first_pitch_is_wrong(tmp_path: Path) -> None:
    """A beat grid must not consume written leading rests because the first pitch is weak.

    The symbolic Bass part rests for four seconds, but the base alignment maps score time
    zero to the first strong instrument beat, putting the first playable note at 12 s.
    The real entrance is 7.3 s.  A later duplicate phrase at 12 s makes the unshifted map
    plausible, while the first real audio note has the wrong pitch estimate.  Timing of the
    following sequence still proves the earlier edge.
    """

    project = tmp_path / "song"
    (project / "analysis").mkdir(parents=True)
    (project / "sources").mkdir(parents=True)
    source_path = project / "sources" / "bass.json"

    pattern = [40, 43, 45, 43, 40, 43, 45, 43]
    source_notes = [_symbolic(4.0 + index * 0.5, midi) for index, midi in enumerate(pattern)]
    ImportedSource(
        provenance=SourceProvenance(
            source_type="guitarpro",
            source_filename="leading-rest.gp5",
            source_sha256="a" * 64,
            importer="fixture",
            importer_version="1",
        ),
        beat_times_seconds=[index * 0.5 for index in range(40)],
        tracks=[
            SourceTrack(
                source_track_index=2,
                name="Bass",
                instrument="bass",
                notes=source_notes,
            )
        ],
    ).write_json(source_path)

    AlignmentReport(
        source_path=str(source_path),
        source_sha256="a" * 64,
        recording_sha256="b" * 64,
        track_index=2,
        audio_beat_start_index=0,
        global_offset_seconds=8.0,
        anchor_stride_beats=8,
        matched_beats=40,
        rms_residual_seconds=0.0,
        median_abs_residual_seconds=0.0,
        max_abs_residual_seconds=0.0,
        confidence=0.9,
        anchors=[
            AlignmentAnchor(
                source_time_seconds=float(source),
                audio_time_seconds=float(source) + 8.0,
                source_beat_index=index,
                audio_beat_index=index,
                confidence=0.9,
            )
            for index, source in enumerate((0, 4, 8, 12, 16))
        ],
        regions=[
            AlignmentRegion(
                source_start_seconds=0.0,
                source_end_seconds=16.0,
                audio_start_seconds=8.0,
                audio_end_seconds=24.0,
                rms_residual_seconds=0.0,
                max_abs_residual_seconds=0.0,
                confidence=0.9,
            )
        ],
    ).write_json(project / "analysis" / "alignment.json")

    early = [
        _audio(7.3 + index * 0.5, 99 if index == 0 else midi, pitch_confidence=0.20 if index == 0 else 0.95)
        for index, midi in enumerate(pattern)
    ]
    later = [_audio(12.0 + index * 0.5, midi) for index, midi in enumerate(pattern)]
    write_transcription(
        BassTranscription(
            engine="fixture",
            source_path="fixture.wav",
            sample_rate_hz=44100,
            notes=[*early, *later],
        ),
        project / "analysis" / "bass_raw.json",
    )

    record = refine_project_alignment_from_leading_rest(project, source_path)

    assert record.applied is True
    assert record.shift_seconds == pytest.approx(-4.7, abs=0.051)
    refined = AlignmentReport.model_validate_json(
        (project / "analysis" / "alignment.json").read_text(encoding="utf-8")
    )
    assert map_source_time(refined, source_notes[0].start_seconds) == pytest.approx(7.3, abs=0.051)
    assert record.refined_onset_matches >= 6
    assert record.reason.startswith("Applied")


def test_leading_rest_refinement_does_not_move_score_without_material_prefix(tmp_path: Path) -> None:
    project = tmp_path / "song"
    (project / "analysis").mkdir(parents=True)
    (project / "sources").mkdir(parents=True)
    source_path = project / "sources" / "bass.json"
    source_notes = [_symbolic(0.5 + index * 0.5, 40 + index % 2) for index in range(8)]
    ImportedSource(
        provenance=SourceProvenance(
            source_type="guitarpro",
            source_filename="no-prefix.gp5",
            source_sha256="c" * 64,
            importer="fixture",
            importer_version="1",
        ),
        beat_times_seconds=[index * 0.5 for index in range(20)],
        tracks=[SourceTrack(source_track_index=1, name="Bass", instrument="bass", notes=source_notes)],
    ).write_json(source_path)
    AlignmentReport(
        source_path=str(source_path),
        source_sha256="c" * 64,
        recording_sha256="d" * 64,
        track_index=1,
        audio_beat_start_index=0,
        global_offset_seconds=2.0,
        anchor_stride_beats=4,
        matched_beats=20,
        rms_residual_seconds=0.0,
        median_abs_residual_seconds=0.0,
        max_abs_residual_seconds=0.0,
        confidence=0.9,
        anchors=[
            AlignmentAnchor(
                source_time_seconds=float(source),
                audio_time_seconds=float(source) + 2.0,
                source_beat_index=index,
                audio_beat_index=index,
                confidence=0.9,
            )
            for index, source in enumerate((0, 2, 4, 6, 8))
        ],
        regions=[
            AlignmentRegion(
                source_start_seconds=0.0,
                source_end_seconds=8.0,
                audio_start_seconds=2.0,
                audio_end_seconds=10.0,
                rms_residual_seconds=0.0,
                max_abs_residual_seconds=0.0,
                confidence=0.9,
            )
        ],
    ).write_json(project / "analysis" / "alignment.json")
    write_transcription(
        BassTranscription(
            engine="fixture",
            source_path="fixture.wav",
            sample_rate_hz=44100,
            notes=[_audio(2.5 + index * 0.5, 40 + index % 2) for index in range(8)],
        ),
        project / "analysis" / "bass_raw.json",
    )

    record = refine_project_alignment_from_leading_rest(project, source_path)
    assert record.applied is False
    assert record.shift_seconds == 0.0
