from __future__ import annotations

from pathlib import Path

import pytest

from rocksmith_cdlc_generator.alignment import (
    AlignmentAnchor,
    AlignmentRegion,
    AlignmentReport,
    map_source_time,
)
from rocksmith_cdlc_generator.alignment_onset_refinement import (
    CURRENT_ALIGNMENT_REFINEMENT_VERSION,
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


def test_periodic_riff_uses_supported_leading_edge_instead_of_later_repetition(
    tmp_path: Path,
) -> None:
    """A repeating intro must not prefer a later measure-spaced translation.

    Both 0 s and -4 s translations can match all eight symbolic notes because the audio
    contains the same two-note riff before the score's current projection. The complete
    score begins with that riff, so the earliest reliable equal-pitch onset plus the
    following sequence is the disambiguating evidence.
    """

    project = tmp_path / "song"
    (project / "analysis").mkdir(parents=True)
    (project / "sources").mkdir(parents=True)
    source_path = project / "sources" / "bass.json"

    pattern = [40, 43] * 4
    symbolic = [_symbolic(12.0 + 2.0 * index, midi) for index, midi in enumerate(pattern)]
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
                notes=symbolic,
            )
        ],
    ).write_json(source_path)

    AlignmentReport(
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
            AlignmentAnchor(
                source_time_seconds=float(value),
                audio_time_seconds=float(value),
                source_beat_index=value,
                audio_beat_index=value,
                confidence=0.9,
            )
            for value in (0, 10, 20, 30, 39)
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
    ).write_json(project / "analysis" / "alignment.json")

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

    record = refine_project_alignment_from_bass_onsets(project, source_path)

    assert record.algorithm_version == CURRENT_ALIGNMENT_REFINEMENT_VERSION
    assert record.applied is True
    assert record.shift_seconds == pytest.approx(-4.0, abs=0.051)
    refined = AlignmentReport.model_validate_json(
        (project / "analysis" / "alignment.json").read_text(encoding="utf-8")
    )
    assert map_source_time(refined, symbolic[0].start_seconds) == pytest.approx(8.0)
    assert "leading-edge support" in record.reason
