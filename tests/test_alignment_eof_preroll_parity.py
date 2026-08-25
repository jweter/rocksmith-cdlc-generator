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
        note_name=None,
        string_index=0,
        fret=max(0, midi - 40),
        import_confidence=1.0,
        trust_class=SourceTrustClass.symbolic_unverified,
        review_required=False,
    )


def _audio(start: float, midi: int, *, review_required: bool = True) -> NoteEvent:
    return NoteEvent(
        start=start,
        duration=0.25,
        midi=midi,
        confidence=0.78,
        pitch_confidence=0.70,
        timing_confidence=0.95,
        review_required=review_required,
    )


def _write_source(project: Path, starts: list[float], midis: list[int]) -> Path:
    source_path = project / "sources" / "bass.json"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    ImportedSource(
        provenance=SourceProvenance(
            source_type="gp3",
            source_filename="fixture.gp3",
            source_sha256="a" * 64,
            importer="fixture",
            importer_version="1",
        ),
        beat_times_seconds=[float(index) for index in range(50)],
        tracks=[
            SourceTrack(
                source_track_index=2,
                name="Bass",
                instrument="bass",
                notes=[_symbolic(start, midi) for start, midi in zip(starts, midis)],
            )
        ],
    ).write_json(source_path)
    return source_path


def _write_alignment(project: Path, *, audio_offset: float) -> None:
    anchors = [
        AlignmentAnchor(
            source_time_seconds=float(source),
            audio_time_seconds=float(source) + audio_offset,
            source_beat_index=source,
            audio_beat_index=source,
            confidence=0.9,
        )
        for source in (0, 10, 20, 30, 40)
    ]
    report = AlignmentReport(
        source_path=str((project / "sources" / "bass.json").resolve()),
        source_sha256="a" * 64,
        recording_sha256="b" * 64,
        track_index=2,
        audio_beat_start_index=0,
        global_offset_seconds=audio_offset,
        anchor_stride_beats=10,
        matched_beats=41,
        rms_residual_seconds=0.0,
        median_abs_residual_seconds=0.0,
        max_abs_residual_seconds=0.0,
        confidence=0.9,
        anchors=anchors,
        regions=[
            AlignmentRegion(
                source_start_seconds=first.source_time_seconds,
                source_end_seconds=second.source_time_seconds,
                audio_start_seconds=first.audio_time_seconds,
                audio_end_seconds=second.audio_time_seconds,
                rms_residual_seconds=0.0,
                max_abs_residual_seconds=0.0,
                confidence=0.9,
            )
            for first, second in zip(anchors, anchors[1:])
        ],
    )
    (project / "analysis").mkdir(parents=True, exist_ok=True)
    report.write_json(project / "analysis" / "alignment.json")


def _write_audio(project: Path, starts: list[float], midis: list[int]) -> None:
    write_transcription(
        BassTranscription(
            engine="fixture",
            source_path="fixture.wav",
            sample_rate_hz=44100,
            notes=[_audio(start, midi) for start, midi in zip(starts, midis)],
        ),
        project / "analysis" / "bass_raw.json",
    )


def test_eof_parity_allows_score_preroll_before_audio_zero(tmp_path: Path) -> None:
    """A valid -9 s correction may put only leading score beats before recording zero."""

    project = tmp_path / "song"
    midis = list(range(40, 48))
    source_path = _write_source(project, [17.0 + index for index in range(8)], midis)
    _write_alignment(project, audio_offset=0.0)
    _write_audio(project, [8.0 + index for index in range(8)], midis)

    record = refine_project_alignment_from_bass_onsets(project, source_path)

    assert record.applied is True
    assert record.algorithm_version == CURRENT_ALIGNMENT_REFINEMENT_VERSION == 2
    assert record.shift_seconds == pytest.approx(-9.0, abs=0.051)
    assert record.candidate_count <= 65

    refined = AlignmentReport.model_validate_json(
        (project / "analysis" / "alignment.json").read_text(encoding="utf-8")
    )
    assert all(anchor.audio_time_seconds >= 0.0 for anchor in refined.anchors)
    assert refined.anchors[0].source_time_seconds == pytest.approx(10.0)
    assert refined.anchors[0].audio_time_seconds == pytest.approx(1.0)
    assert map_source_time(refined, 17.0) == pytest.approx(8.0, abs=0.051)


def test_eof_parity_removes_double_counted_recording_intro(tmp_path: Path) -> None:
    """Do not add a detected recording intro on top of GP leading-measure time."""

    project = tmp_path / "song"
    midis = list(range(40, 48))
    starts = [8.0 + index for index in range(8)]
    source_path = _write_source(project, starts, midis)
    _write_alignment(project, audio_offset=9.0)
    _write_audio(project, starts, midis)

    record = refine_project_alignment_from_bass_onsets(project, source_path)

    assert record.applied is True
    assert record.shift_seconds == pytest.approx(-9.0, abs=0.051)

    refined = AlignmentReport.model_validate_json(
        (project / "analysis" / "alignment.json").read_text(encoding="utf-8")
    )
    assert refined.global_offset_seconds == pytest.approx(0.0, abs=0.051)
    assert map_source_time(refined, 8.0) == pytest.approx(8.0, abs=0.051)
    assert map_source_time(refined, 15.0) == pytest.approx(15.0, abs=0.051)


def test_jittered_onsets_are_one_shift_neighborhood_not_competing_winners(tmp_path: Path) -> None:
    """Small real-world onset jitter must not make the correct shift tie with itself."""

    project = tmp_path / "song"
    midis = list(range(40, 48))
    source_starts = [17.0 + index for index in range(8)]
    jitter = [-0.03, 0.02, -0.01, 0.04, -0.02, 0.01, 0.03, -0.04]
    audio_starts = [8.0 + index + jitter[index] for index in range(8)]
    source_path = _write_source(project, source_starts, midis)
    _write_alignment(project, audio_offset=0.0)
    _write_audio(project, audio_starts, midis)

    record = refine_project_alignment_from_bass_onsets(project, source_path)

    assert record.applied is True
    assert record.shift_seconds == pytest.approx(-9.0, abs=0.11)
    refined = AlignmentReport.model_validate_json(
        (project / "analysis" / "alignment.json").read_text(encoding="utf-8")
    )
    assert map_source_time(refined, source_starts[0]) == pytest.approx(
        audio_starts[0], abs=0.16
    )


def test_translation_preserves_weak_region_confidence(tmp_path: Path) -> None:
    """A translation-only fix must never upgrade weak local alignment evidence."""

    project = tmp_path / "song"
    midis = list(range(40, 48))
    source_path = _write_source(project, [17.0 + index for index in range(8)], midis)
    _write_alignment(project, audio_offset=0.0)

    alignment_path = project / "analysis" / "alignment.json"
    original = AlignmentReport.model_validate_json(alignment_path.read_text(encoding="utf-8"))
    regions = list(original.regions)
    regions[1] = regions[1].model_copy(
        update={
            "confidence": 0.35,
            "rms_residual_seconds": 0.08,
            "max_abs_residual_seconds": 0.14,
        }
    )
    original.model_copy(update={"regions": regions}).write_json(alignment_path)
    _write_audio(project, [8.0 + index for index in range(8)], midis)

    record = refine_project_alignment_from_bass_onsets(project, source_path)

    assert record.applied is True
    refined = AlignmentReport.model_validate_json(alignment_path.read_text(encoding="utf-8"))
    weak = next(
        region
        for region in refined.regions
        if region.source_start_seconds <= 10.0 + 1e-6
        and region.source_end_seconds >= 20.0 - 1e-6
    )
    assert weak.confidence == pytest.approx(0.35)
    assert weak.rms_residual_seconds == pytest.approx(0.08)
    assert weak.max_abs_residual_seconds == pytest.approx(0.14)
