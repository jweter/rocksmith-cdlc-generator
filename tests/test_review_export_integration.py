from pathlib import Path

from rocksmith_cdlc_generator.beats import BeatEvent, TempoMap, write_tempo_map
from rocksmith_cdlc_generator.cli import build_parser
from rocksmith_cdlc_generator.fret_mapping import BassMapping, MappedNote, write_bass_mapping
from rocksmith_cdlc_generator.fretboard import E_STANDARD
from rocksmith_cdlc_generator.models import AudioMetadata, ProjectManifest
from rocksmith_cdlc_generator.reconciliation import SourceDisagreement, SourceDisagreementReport
from rocksmith_cdlc_generator.rocksmith_xml import build_rocksmith_bass_xml
from rocksmith_cdlc_generator.transcription import BassTranscription, NoteEvent, write_transcription
from rocksmith_cdlc_generator.validation import validate_project


def _manifest(project: Path) -> ProjectManifest:
    project.mkdir(parents=True, exist_ok=True)
    manifest = ProjectManifest(
        project_name="integration-test",
        artist="Test Artist",
        title="Test Song",
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
    )
    manifest.save(project)
    return manifest


def _tempo() -> TempoMap:
    return TempoMap(
        engine="test",
        beats=[
            BeatEvent(time=0.5, beat=1, measure=1, bpm=120.0, confidence=0.95, is_downbeat=True),
            BeatEvent(time=1.0, beat=2, measure=1, bpm=120.0, confidence=0.95),
            BeatEvent(time=1.5, beat=3, measure=1, bpm=120.0, confidence=0.95),
            BeatEvent(time=2.0, beat=4, measure=1, bpm=120.0, confidence=0.95),
        ],
    )


def _write_valid_base(project: Path, mapping: BassMapping) -> None:
    _manifest(project)
    write_tempo_map(_tempo(), project / "analysis" / "tempo_map.json")
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
    write_bass_mapping(mapping, project / "charts" / "bass_mapped.json")


def test_cli_exposes_mapping_source_selection() -> None:
    parser = build_parser()
    args = parser.parse_args(["map-bass", "project", "--source", "reconciled"])
    assert args.source == "reconciled"


def test_supported_imported_techniques_are_exported_to_rocksmith_xml(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path / "project")
    mapping = BassMapping(
        tuning=E_STANDARD,
        max_fret=24,
        notes=[
            MappedNote(
                start=1.0,
                duration=0.4,
                midi=40,
                string=0,
                fret=12,
                source_confidence=0.95,
                mapping_confidence=1.0,
                position_source="symbolic",
                techniques=["palm_mute", "harmonic", "tremolo_picking", "vibrato", "accent"],
            )
        ],
    )
    root = build_rocksmith_bass_xml(manifest, _tempo(), mapping)
    note = root.find("levels/level/notes/note")
    assert note is not None
    assert note.attrib["palmMute"] == "1"
    assert note.attrib["harmonic"] == "1"
    assert note.attrib["tremolo"] == "1"
    assert note.attrib["vibrato"] == "80"
    assert note.attrib["accent"] == "1"
    properties = root.find("arrangementProperties")
    assert properties is not None
    assert properties.attrib["palmMutes"] == "1"
    assert properties.attrib["harmonics"] == "1"
    assert properties.attrib["tremolo"] == "1"
    assert properties.attrib["vibrato"] == "1"


def test_source_disagreements_and_unsupported_techniques_enter_review_queue(tmp_path: Path) -> None:
    project = tmp_path / "project"
    mapping = BassMapping(
        tuning=E_STANDARD,
        max_fret=24,
        notes=[
            MappedNote(
                start=1.0,
                duration=0.4,
                midi=40,
                string=0,
                fret=12,
                source_confidence=0.95,
                mapping_confidence=0.95,
                techniques=["slide"],
            )
        ],
    )
    _write_valid_base(project, mapping)
    report = SourceDisagreementReport(
        source_sha256="a" * 64,
        track_index=0,
        disagreements=[
            SourceDisagreement(
                status="pitch_conflict",
                audio_start_seconds=1.0,
                symbolic_start_seconds=0.9,
                onset_delta_seconds=0.1,
                symbolic_midi=40,
                audio_midi=41,
                audio_confidence=0.9,
                alignment_confidence=0.9,
                reason="Symbolic and audio-derived notes disagree on pitch.",
            )
        ],
    )
    review_path = project / "review" / "source_disagreements.json"
    review_path.parent.mkdir(parents=True, exist_ok=True)
    review_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")

    validation = validate_project(project)
    codes = {item.code for item in validation.review_queue}
    assert validation.status == "WARNING"
    assert validation.can_package is True
    assert "source_pitch_conflict" in codes
    assert "unsupported_imported_technique" in codes
