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
    leading_rest_refinement_is_current,
)
from rocksmith_cdlc_generator.alignment_onset_refinement import refinement_is_current
from rocksmith_cdlc_generator.eof_first_sync_alignment import (
    EOF_UPSTREAM_COMMIT,
    eof_first_sync_alignment_is_current,
    refine_project_alignment_from_eof_first_sync,
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


def _write_source(project: Path, starts: list[float]) -> Path:
    source_path = project / "sources" / "bass.json"
    pattern = [40, 43, 45, 43, 40, 43, 45, 43]
    ImportedSource(
        provenance=SourceProvenance(
            source_type="guitarpro",
            source_filename="fixture.gp5",
            source_sha256="a" * 64,
            importer="fixture",
            importer_version="1",
        ),
        beat_times_seconds=[index * 0.5 for index in range(48)],
        tracks=[
            SourceTrack(
                source_track_index=2,
                name="Bass",
                instrument="bass",
                notes=[_symbolic(start, pattern[index % len(pattern)]) for index, start in enumerate(starts)],
            )
        ],
    ).write_json(source_path)
    return source_path


def _write_alignment(project: Path, source_path: Path, *, offset: float) -> AlignmentReport:
    anchors = [
        AlignmentAnchor(
            source_time_seconds=source,
            audio_time_seconds=source + offset,
            source_beat_index=index * 8,
            audio_beat_index=index * 8,
            confidence=0.95,
        )
        for index, source in enumerate((0.0, 4.0, 8.0, 12.0, 16.0, 20.0))
    ]
    report = AlignmentReport(
        source_path=str(source_path),
        source_sha256="a" * 64,
        recording_sha256="b" * 64,
        track_index=2,
        audio_beat_start_index=0,
        global_offset_seconds=offset,
        anchor_stride_beats=8,
        matched_beats=48,
        rms_residual_seconds=0.0,
        median_abs_residual_seconds=0.0,
        max_abs_residual_seconds=0.0,
        confidence=0.95,
        anchors=anchors,
        regions=[
            AlignmentRegion(
                source_start_seconds=0.0,
                source_end_seconds=20.0,
                audio_start_seconds=offset,
                audio_end_seconds=20.0 + offset,
                rms_residual_seconds=0.0,
                max_abs_residual_seconds=0.0,
                confidence=0.95,
            )
        ],
    )
    report.write_json(project / "analysis" / "alignment.json")
    return report


def test_eof_first_sync_chooses_earliest_supported_prefix_not_late_repeat(tmp_path: Path) -> None:
    """Regression for the packaged 11.773s -> 7.109s Product Reality failure.

    The current beat transform projects the first playable source event to 11.773s. The
    recording contains the real onset sequence at 7.109s and a later repeated occurrence at
    11.773s. The old periodic ranking can bind the later repetition; the EOF first-sync path
    must bind the complete score to the earliest strongly supported occurrence instead.
    """

    project = tmp_path / "song"
    (project / "analysis").mkdir(parents=True)
    (project / "sources").mkdir(parents=True)

    source_starts = [4.0 + index * 0.5 for index in range(8)]
    source_path = _write_source(project, source_starts)
    _write_alignment(project, source_path, offset=7.773)

    pattern = [40, 43, 45, 43, 40, 43, 45, 43]
    early = [
        _audio(
            7.109 + index * 0.5,
            99 if index == 0 else midi,
            pitch_confidence=0.20 if index == 0 else 0.95,
        )
        for index, midi in enumerate(pattern)
    ]
    late_repeat = [
        _audio(11.773 + index * 0.5, midi)
        for index, midi in enumerate(pattern)
    ]
    write_transcription(
        BassTranscription(
            engine="fixture",
            source_path="fixture.wav",
            sample_rate_hz=44100,
            notes=[*early, *late_repeat],
        ),
        project / "analysis" / "bass_raw.json",
    )

    record = refine_project_alignment_from_eof_first_sync(project, source_path)

    assert record.applied is True
    assert record.upstream_commit == EOF_UPSTREAM_COMMIT
    assert record.matched_first_playable_seconds == pytest.approx(7.109, abs=0.001)
    assert record.shift_seconds == pytest.approx(-4.664, abs=0.001)
    assert record.matched_onset_count >= 6

    refined = AlignmentReport.model_validate_json(
        (project / "analysis" / "alignment.json").read_text(encoding="utf-8")
    )
    assert map_source_time(refined, 4.0) == pytest.approx(7.109, abs=0.001)
    assert eof_first_sync_alignment_is_current(project, refined) is True

    # The existing workflow planner still checks these legacy currency files. They are
    # explicit no-op compatibility markers, not executed heuristic corrections.
    assert refinement_is_current(project, refined) is True
    assert leading_rest_refinement_is_current(project, refined) is True
    onset_marker = (project / "analysis" / "alignment_onset_refinement.json").read_text(encoding="utf-8")
    leading_marker = (project / "analysis" / "alignment_leading_rest_refinement.json").read_text(encoding="utf-8")
    assert "Compatibility completion marker only" in onset_marker
    assert "Compatibility completion marker only" in leading_marker


def test_eof_first_sync_fails_closed_without_supported_prefix(tmp_path: Path) -> None:
    project = tmp_path / "song"
    (project / "analysis").mkdir(parents=True)
    (project / "sources").mkdir(parents=True)

    source_starts = [4.0 + index * 0.5 for index in range(8)]
    source_path = _write_source(project, source_starts)
    baseline = _write_alignment(project, source_path, offset=7.773)

    # Sparse unrelated timing evidence cannot establish the beginning of the score.
    write_transcription(
        BassTranscription(
            engine="fixture",
            source_path="fixture.wav",
            sample_rate_hz=44100,
            notes=[
                _audio(2.0, 50),
                _audio(5.3, 52),
                _audio(9.9, 55),
            ],
        ),
        project / "analysis" / "bass_raw.json",
    )

    record = refine_project_alignment_from_eof_first_sync(project, source_path)

    assert record.applied is False
    assert record.matched_first_playable_seconds is None
    unchanged = AlignmentReport.model_validate_json(
        (project / "analysis" / "alignment.json").read_text(encoding="utf-8")
    )
    assert map_source_time(unchanged, 4.0) == pytest.approx(map_source_time(baseline, 4.0))
    assert eof_first_sync_alignment_is_current(project, unchanged) is True
    assert not (project / "analysis" / "alignment_onset_refinement.json").exists()
    assert not (project / "analysis" / "alignment_leading_rest_refinement.json").exists()
