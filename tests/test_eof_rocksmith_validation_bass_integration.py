from pathlib import Path

from rocksmith_cdlc_generator.beats import BeatEvent, TempoMap, write_tempo_map
from rocksmith_cdlc_generator.fret_mapping import BassMapping, MappedNote, write_bass_mapping
from rocksmith_cdlc_generator.fretboard import E_STANDARD
from rocksmith_cdlc_generator.models import AudioMetadata, ProjectManifest
from rocksmith_cdlc_generator.transcription import BassTranscription, NoteEvent, write_transcription
from rocksmith_cdlc_generator.validation import validate_project


def _write_project(project: Path, mapped_note: MappedNote, *, max_fret: int) -> None:
    project.mkdir(parents=True, exist_ok=True)
    ProjectManifest(
        project_name="eof-bass-validation-test",
        artist="Test",
        title="Test",
        source_original_path="source.wav",
        source_project_path="source/source.wav",
        source_sha256="0" * 64,
        source_metadata=AudioMetadata(
            duration_seconds=8.0,
            sample_rate_hz=44100,
            channels=2,
            codec_name="pcm_s16le",
            format_name="wav",
        ),
    ).save(project)
    write_tempo_map(
        TempoMap(
            engine="test",
            beats=[
                BeatEvent(
                    time=0.5,
                    beat=1,
                    measure=1,
                    bpm=120.0,
                    confidence=0.9,
                    is_downbeat=True,
                ),
                BeatEvent(
                    time=1.0,
                    beat=2,
                    measure=1,
                    bpm=120.0,
                    confidence=0.9,
                ),
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
                    start=mapped_note.start,
                    duration=mapped_note.duration,
                    midi=mapped_note.midi,
                    confidence=0.9,
                    pitch_confidence=0.9,
                    timing_confidence=0.9,
                )
            ],
        ),
        project / "analysis" / "bass_raw.json",
    )
    write_bass_mapping(
        BassMapping(tuning=E_STANDARD, max_fret=max_fret, notes=[mapped_note]),
        project / "charts" / "bass_mapped.json",
    )


def test_bass_fret_above_24_is_a_rocksmith_blocker(tmp_path: Path) -> None:
    midi = E_STANDARD.open_midi[0] + 25
    note = MappedNote(
        start=1.0,
        duration=0.4,
        midi=midi,
        string=0,
        fret=25,
        source_confidence=0.9,
        mapping_confidence=0.9,
    )
    project = tmp_path / "project"
    _write_project(project, note, max_fret=30)

    report = validate_project(project)

    assert report.status == "FAIL"
    assert any(
        item.code == "rocksmith_fret_limit_exceeded"
        and item.severity == "FAIL"
        for item in report.review_queue
    )


def test_bass_open_string_bend_gets_targeted_eof_findings(tmp_path: Path) -> None:
    note = MappedNote(
        start=1.0,
        duration=0.4,
        midi=E_STANDARD.open_midi[3],
        string=3,
        fret=0,
        source_confidence=0.9,
        mapping_confidence=0.9,
        techniques=["bend"],
    )
    project = tmp_path / "project"
    _write_project(project, note, max_fret=24)

    report = validate_project(project)
    codes = {item.code for item in report.review_queue}

    assert report.status == "WARNING"
    assert "rocksmith_open_string_bend" in codes
    assert "rocksmith_bend_detail_missing" in codes
    assert not any(
        item.code == "unsupported_imported_technique" and "bend" in item.message
        for item in report.review_queue
    )
