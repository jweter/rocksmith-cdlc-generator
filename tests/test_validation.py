import json
from pathlib import Path

from rocksmith_cdlc_generator.alignment import AlignmentAnchor, CURRENT_ALIGNMENT_METHOD
from rocksmith_cdlc_generator.beats import BeatEvent, TempoMap, write_tempo_map
from rocksmith_cdlc_generator.fret_mapping import BassMapping, MappedNote, write_bass_mapping
from rocksmith_cdlc_generator.fretboard import E_STANDARD
from rocksmith_cdlc_generator.hashing import sha256_file
from rocksmith_cdlc_generator.human_review_marks import mark_event
from rocksmith_cdlc_generator.models import AudioMetadata, ProjectManifest
from rocksmith_cdlc_generator.score_fanout import ScoreFanoutEntry, ScoreFanoutManifest
from rocksmith_cdlc_generator.score_source import (
    ArrangementRole,
    ProjectScoreSource,
    ScoreArrangementMapping,
    ScoreTrackCandidate,
)
from rocksmith_cdlc_generator.shared_timeline import SharedTimeline
from rocksmith_cdlc_generator.source_import import ImportedSource, SourceNoteEvent, SourceProvenance, SourceTrack
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


def _register_bass_score_and_mark(project: Path, *, state: str) -> None:
    """Register current Bass score/fan-out/timing authority and record one human mark.

    #379-#382 review finding #1: previously a `wrong` mark on a Bass event never made it
    into ``validate_project``'s output at all, unlike Lead/Rhythm's guitar_validation.py.
    #425 adds score-coverage validation, so this integration fixture now includes a
    deterministic identity shared timeline rather than leaving registered authority
    intentionally incomplete and accidentally testing the coverage failure path.
    """

    stored = project / "sources" / "score" / "original" / "song.gp5"
    stored.parent.mkdir(parents=True, exist_ok=True)
    stored.write_bytes(b"complete-score")
    digest = sha256_file(stored)
    score = ProjectScoreSource(
        source_filename="song.gp5",
        source_sha256=digest,
        source_format="gp5",
        imported_relative_path=stored.relative_to(project).as_posix(),
        tracks=[ScoreTrackCandidate(source_track_index=0, name="Bass", note_count=1)],
        arrangement_mappings=[
            ScoreArrangementMapping(role=ArrangementRole.bass, source_track_index=0, confidence=1.0, human_confirmed=True)
        ],
    )
    score.write_json(project / "sources" / "score" / "source.json")

    output = project / "sources" / "imported" / "bass.json"
    ImportedSource(
        provenance=SourceProvenance(
            source_type="gp5", source_filename="song.gp5", source_sha256=digest, importer="test", importer_version="1"
        ),
        beat_times_seconds=[0.0, 10.0],
        tracks=[
            SourceTrack(
                source_track_index=0,
                instrument="bass",
                notes=[SourceNoteEvent(start_seconds=1.0, duration_seconds=0.4, midi=40, import_confidence=0.9)],
            )
        ],
    ).write_json(output)
    manifest = ScoreFanoutManifest(
        score_source_sha256=digest,
        score_source_format="gp5",
        arrangements=[ScoreFanoutEntry(role=ArrangementRole.bass, source_track_index=0, output_json=output.relative_to(project).as_posix())],
    )
    (project / "sources" / "imported" / f"score-fanout-{digest[:12]}.json").write_text(
        manifest.model_dump_json(indent=2), encoding="utf-8"
    )
    SharedTimeline(
        method=CURRENT_ALIGNMENT_METHOD,
        recording_sha256="0" * 64,
        score_sha256=digest,
        authority_role=ArrangementRole.bass,
        authority_track_index=0,
        authority_output_json=output.relative_to(project).as_posix(),
        authority_output_sha256=sha256_file(output),
        inherited_roles=[ArrangementRole.bass],
        audio_beat_start_index=0,
        global_offset_seconds=0.0,
        anchor_stride_beats=1,
        matched_beats=2,
        rms_residual_seconds=0.0,
        median_abs_residual_seconds=0.0,
        max_abs_residual_seconds=0.0,
        confidence=1.0,
        anchors=[
            AlignmentAnchor(
                source_time_seconds=0.0,
                audio_time_seconds=0.0,
                source_beat_index=0,
                audio_beat_index=0,
                confidence=1.0,
            ),
            AlignmentAnchor(
                source_time_seconds=10.0,
                audio_time_seconds=10.0,
                source_beat_index=1,
                audio_beat_index=1,
                confidence=1.0,
            ),
        ],
        regions=[],
    ).write_json(project / "analysis" / "shared_timeline.json")

    mark_event(
        project,
        source_sha256=digest,
        arrangement="bass",
        event_index=0,
        source_start_seconds=1.0,
        midi=40,
        string_index=0,
        fret=12,
        state=state,
    )


def test_bass_wrong_mark_blocks_packaging(tmp_path: Path) -> None:
    """#1: a `wrong` mark on a Bass event must block packaging the same way it already
    does for Lead/Rhythm in guitar_validation.py, not silently pass the packaging gate."""

    project = tmp_path / "project"
    _write_manifest(project)
    _write_valid_artifacts(project)
    assert validate_project(project).can_package is True

    _register_bass_score_and_mark(project, state="wrong")

    report = validate_project(project)
    assert report.status == "FAIL"
    assert report.can_package is False
    assert any(item.code == "human_mark_wrong" for item in report.review_queue)


def test_bass_questionable_mark_warns_but_does_not_block_packaging(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_manifest(project)
    _write_valid_artifacts(project)

    _register_bass_score_and_mark(project, state="questionable")

    report = validate_project(project)
    assert report.status == "WARNING"
    assert report.can_package is True
    assert any(item.code == "human_mark_questionable" for item in report.review_queue)


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
