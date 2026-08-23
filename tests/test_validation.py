import json
from pathlib import Path

from rocksmith_cdlc_generator.beats import BeatEvent, TempoMap, write_tempo_map
from rocksmith_cdlc_generator.fret_mapping import BassMapping, MappedNote, write_bass_mapping
from rocksmith_cdlc_generator.fretboard import E_STANDARD
from rocksmith_cdlc_generator.models import AudioMetadata, ProjectManifest
from rocksmith_cdlc_generator.transcription import BassTranscription, NoteEvent, write_transcription
from rocksmith_cdlc_generator.validation import (
    ReviewItem,
    ValidationReport,
    count_actionable_warnings,
    format_actionable_warning_compact,
    format_actionable_warning_summary,
    validate_project,
    write_review_artifacts,
)


def _write_manifest(project: Path, duration: float = 10.0) -> None:
    project.mkdir(parents=True, exist_ok=True)
    manifest = ProjectManifest(
        project_name="validation-test",
        artist="Test",
        title="Validation Test",
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
    )
    manifest.save(project)


def _write_valid_artifacts(project: Path) -> None:
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
    transcription = BassTranscription(
        engine="test",
        source_path="audio.wav",
        sample_rate_hz=44100,
        notes=[
            NoteEvent(start=1.0, duration=0.4, midi=40, confidence=0.9, pitch_confidence=0.9, timing_confidence=0.9),
            NoteEvent(start=2.0, duration=0.4, midi=43, confidence=0.9, pitch_confidence=0.9, timing_confidence=0.9),
        ],
    )
    write_transcription(transcription, project / "analysis" / "bass_raw.json")
    write_bass_mapping(
        BassMapping(
            tuning=E_STANDARD,
            max_fret=24,
            notes=[
                MappedNote(start=1.0, duration=0.4, midi=40, string=0, fret=12, source_confidence=0.9, mapping_confidence=0.9),
                MappedNote(start=2.0, duration=0.4, midi=43, string=3, fret=0, source_confidence=0.9, mapping_confidence=0.9),
            ],
        ),
        project / "charts" / "bass_mapped.json",
    )


def test_valid_project_passes(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_manifest(project)
    _write_valid_artifacts(project)
    report = validate_project(project)
    assert report.status == "PASS"
    assert report.can_package is True
    assert report.fail_count == 0
    assert report.warning_count == 0
    assert report.review_queue == []


def test_missing_artifacts_block_packaging(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_manifest(project)
    report = validate_project(project)
    assert report.status == "FAIL"
    assert report.can_package is False
    assert report.fail_count == 3
    assert {item.code for item in report.review_queue} == {"missing_tempo", "missing_transcription", "missing_mapping"}


def test_review_queue_prioritizes_failures_and_uncertain_notes(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_manifest(project, duration=3.0)
    write_tempo_map(
        TempoMap(
            engine="test",
            beats=[
                BeatEvent(time=0.5, beat=1, measure=1, bpm=120.0, confidence=0.2, is_downbeat=True),
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
            notes=[NoteEvent(start=1.0, duration=0.5, midi=40, confidence=0.3, pitch_confidence=0.3, timing_confidence=0.9, review_required=True)],
        ),
        project / "analysis" / "bass_raw.json",
    )
    write_bass_mapping(
        BassMapping(
            tuning=E_STANDARD,
            max_fret=24,
            notes=[MappedNote(start=1.0, duration=0.5, midi=20, source_confidence=0.3, mapping_confidence=0.0, review_required=True)],
        ),
        project / "charts" / "bass_mapped.json",
    )
    report = validate_project(project)
    assert report.status == "FAIL"
    assert report.can_package is False
    assert report.review_queue[0].severity == "FAIL"
    assert report.review_queue[0].code == "unmapped_bass_note"
    codes = {item.code for item in report.review_queue}
    assert "low_beat_confidence" in codes
    assert "bass_note_requires_review" in codes


def test_review_artifacts_are_written(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_manifest(project)
    _write_valid_artifacts(project)
    report = validate_project(project)
    outputs = write_review_artifacts(report, project)
    assert set(outputs) == {"validation", "flags", "summary"}
    assert outputs["validation"].is_file()
    assert outputs["flags"].read_text(encoding="utf-8").strip() == "[]"
    summary = outputs["summary"].read_text(encoding="utf-8")
    assert "**Status:** PASS" in summary
    assert "No unresolved review items." in summary


def _repeated_warning(index: int) -> ReviewItem:
    return ReviewItem(
        code="source_pitch_conflict",
        severity="WARNING",
        stage="reconciliation",
        message="Symbolic and audio-derived notes occur together but disagree on MIDI pitch.",
        time_seconds=float(index),
        priority=90,
    )


def test_count_actionable_warnings_groups_repeated_events_by_root_cause() -> None:
    """#375: a warning flood of thousands of repeated events must count as a
    manageable number of actionable root-cause groups, not raw event volume.
    """
    fail = ReviewItem(
        code="unmapped_bass_note",
        severity="FAIL",
        stage="mapping",
        message="Bass note 10 has no playable string/fret position.",
        time_seconds=4.0,
        priority=100,
    )
    items = [fail, *(_repeated_warning(index) for index in range(2851))]

    assert count_actionable_warnings(items) == 1
    # FAIL is never counted as an actionable "warning" group and is unaffected.
    fail_count = sum(item.severity == "FAIL" for item in items)
    assert fail_count == 1


def test_format_actionable_warning_summary_preserves_raw_total_alongside_groups() -> None:
    assert (
        format_actionable_warning_summary(19, 7878)
        == "19 actionable warning groups · 7878 underlying warning events"
    )
    assert format_actionable_warning_summary(1, 1) == "1 actionable warning group · 1 underlying warning event"
    assert format_actionable_warning_summary(0, 0) == "0 warnings"


def test_format_actionable_warning_compact_pairs_actionable_with_raw() -> None:
    assert format_actionable_warning_compact(19, 7878) == "19/7878"
    assert format_actionable_warning_compact(0, 0) == "0"


def test_summary_markdown_pairs_actionable_groups_with_raw_warning_total(tmp_path: Path) -> None:
    """#375: review/summary.md must never present the raw warning-event total on
    its own -- pairing it with the actionable/grouped count makes clear that raw
    volume is evidence, not remaining manual review work. The raw total itself
    must still be present verbatim for audit/provenance.
    """
    project = tmp_path / "project"
    report = ValidationReport(
        status="WARNING",
        can_package=True,
        fail_count=0,
        warning_count=2851,
        review_queue=[_repeated_warning(index) for index in range(2851)],
    )
    outputs = write_review_artifacts(report, project)
    summary = outputs["summary"].read_text(encoding="utf-8")

    assert "**Warnings:** 1 actionable warning group · 2851 underlying warning events" in summary
    # The complete raw event list remains fully intact in flags.json for audit.
    flags = json.loads(outputs["flags"].read_text(encoding="utf-8"))
    assert len(flags) == 2851
