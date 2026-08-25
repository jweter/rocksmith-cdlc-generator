from pathlib import Path

import pytest

import rocksmith_cdlc_generator.validation as bass_validation
from rocksmith_cdlc_generator.beats import BeatEvent, TempoMap, write_tempo_map
from rocksmith_cdlc_generator.fret_mapping import BassMapping, MappedNote, write_bass_mapping
from rocksmith_cdlc_generator.fretboard import E_STANDARD
from rocksmith_cdlc_generator.models import AudioMetadata, ProjectManifest
from rocksmith_cdlc_generator.score_coverage import (
    ScoreCoverageAssessment,
    assess_mapped_score_coverage,
    partial_score_warning_message,
)
from rocksmith_cdlc_generator.transcription import BassTranscription, NoteEvent, write_transcription


def _write_valid_bass_project(project: Path, *, duration: float = 141.27) -> None:
    project.mkdir(parents=True, exist_ok=True)
    ProjectManifest(
        project_name="score-coverage-test",
        artist="Test Artist",
        title="Test Song",
        source_original_path="source.wav",
        source_project_path="source/source.wav",
        source_sha256="0" * 64,
        source_metadata=AudioMetadata(
            duration_seconds=duration,
            sample_rate_hz=44100,
            channels=2,
            codec_name="pcm_s16le",
            format_name="wav",
        ),
        arrangement_instruments=["bass"],
    ).save(project)
    write_tempo_map(
        TempoMap(
            engine="test",
            beats=[
                BeatEvent(time=0.5, beat=1, measure=1, bpm=120.0, confidence=0.9, is_downbeat=True),
                BeatEvent(time=1.0, beat=2, measure=1, bpm=120.0, confidence=0.9),
            ],
        ),
        project / "analysis" / "tempo_map.json",
    )
    write_transcription(
        BassTranscription(
            engine="test",
            source_path="audio.wav",
            sample_rate_hz=44100,
            notes=[
                NoteEvent(
                    start=1.0,
                    duration=0.4,
                    midi=40,
                    confidence=0.9,
                    pitch_confidence=0.9,
                    timing_confidence=0.9,
                )
            ],
        ),
        project / "analysis" / "bass_raw.json",
    )
    write_bass_mapping(
        BassMapping(
            tuning=E_STANDARD,
            max_fret=24,
            notes=[
                MappedNote(
                    start=1.0,
                    duration=0.4,
                    midi=40,
                    string=0,
                    fret=12,
                    source_confidence=0.9,
                    mapping_confidence=0.9,
                )
            ],
        ),
        project / "charts" / "bass_mapped.json",
    )


def test_partial_coverage_prefers_score_timebase_over_late_note_events() -> None:
    assessment = assess_mapped_score_coverage(
        141.27,
        mapped_score_beats=[0.0, 10.0, 20.0, 43.6],
        mapped_note_end_times=[130.0],
    )

    assert assessment.state == "PARTIAL"
    assert assessment.basis == "mapped_score_timebase"
    assert assessment.score_end_seconds == pytest.approx(43.6)
    assert assessment.covered_percent == pytest.approx(30.8629, rel=1e-4)
    assert assessment.uncovered_tail_seconds == pytest.approx(97.67)


def test_small_recording_tail_is_complete_not_partial() -> None:
    assessment = assess_mapped_score_coverage(
        141.27,
        mapped_score_beats=[0.0, 60.0, 120.0, 136.5],
    )

    assert assessment.state == "COMPLETE"
    assert assessment.basis == "mapped_score_timebase"
    assert assessment.uncovered_tail_seconds == pytest.approx(4.77)
    assert assessment.partial_threshold_seconds == pytest.approx(7.0635)


def test_note_event_extent_is_only_a_fallback_when_score_beats_are_unavailable() -> None:
    assessment = assess_mapped_score_coverage(
        100.0,
        mapped_note_end_times=[20.0, 95.5],
    )

    assert assessment.state == "COMPLETE"
    assert assessment.basis == "mapped_note_events"
    assert assessment.score_end_seconds == pytest.approx(95.5)


def test_partial_warning_reports_extent_without_fabricating_missing_notes() -> None:
    assessment = assess_mapped_score_coverage(
        141.27,
        mapped_score_beats=[43.6],
    )

    message = partial_score_warning_message(assessment)

    assert "43.60s" in message
    assert "141.27s" in message
    assert "30.9% coverage" in message
    assert "97.67s uncovered" in message
    assert "No missing notes were extrapolated or invented" in message


def test_bass_validation_surfaces_partial_score_as_reviewable_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    _write_valid_bass_project(project)
    score_contract = project / "sources" / "score" / "source.json"
    score_contract.parent.mkdir(parents=True, exist_ok=True)
    score_contract.write_text("{}", encoding="utf-8")
    partial = ScoreCoverageAssessment(
        state="PARTIAL",
        basis="mapped_score_timebase",
        recording_duration_seconds=141.27,
        score_end_seconds=43.6,
        covered_percent=(43.6 / 141.27) * 100.0,
        uncovered_tail_seconds=141.27 - 43.6,
        partial_threshold_seconds=141.27 * 0.05,
    )
    monkeypatch.setattr(
        bass_validation,
        "assess_project_score_coverage",
        lambda _project_dir: partial,
    )

    report = bass_validation.validate_project(project)

    assert report.status == "WARNING"
    assert report.can_package is True
    assert report.fail_count == 0
    warnings = [item for item in report.review_queue if item.code == "partial_score_coverage"]
    assert len(warnings) == 1
    assert warnings[0].severity == "WARNING"
    assert warnings[0].stage == "source_coverage"
    assert warnings[0].time_seconds == pytest.approx(43.6)
