from pathlib import Path

from rocksmith_cdlc_generator.beats import BeatEvent, TempoMap, write_tempo_map
from rocksmith_cdlc_generator.fret_mapping import BassMapping, MappedNote, write_bass_mapping
from rocksmith_cdlc_generator.fretboard import E_STANDARD
from rocksmith_cdlc_generator.models import AudioMetadata, ProjectManifest
from rocksmith_cdlc_generator.transcription import BassTranscription, NoteEvent, write_transcription
from rocksmith_cdlc_generator.validation import validate_project, write_review_artifacts


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
