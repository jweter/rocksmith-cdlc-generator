from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from rocksmith_cdlc_generator.authoring_export import export_project_bass_authoring
from rocksmith_cdlc_generator.beats import BeatEvent, TempoMap, write_tempo_map
from rocksmith_cdlc_generator.fret_mapping import BassMapping, MappedNote, write_bass_mapping
from rocksmith_cdlc_generator.fretboard import DROP_D, E_STANDARD
from rocksmith_cdlc_generator.models import AudioMetadata, ProjectManifest
from rocksmith_cdlc_generator.packaging_gate import PackagingBlockedError
from rocksmith_cdlc_generator.rocksmith_xml import build_rocksmith_bass_xml, rocksmith_tuning_offsets
from rocksmith_cdlc_generator.transcription import BassTranscription, NoteEvent, write_transcription


def _manifest(project: Path) -> ProjectManifest:
    project.mkdir(parents=True, exist_ok=True)
    manifest = ProjectManifest(
        project_name="xml-test",
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
        time_signature_numerator=4,
        time_signature_denominator=4,
        beats=[
            BeatEvent(time=0.5, beat=1, measure=1, bpm=120.0, confidence=0.9, is_downbeat=True),
            BeatEvent(time=1.0, beat=2, measure=1, bpm=120.0, confidence=0.9),
            BeatEvent(time=1.5, beat=3, measure=1, bpm=120.0, confidence=0.9),
            BeatEvent(time=2.0, beat=4, measure=1, bpm=120.0, confidence=0.9),
            BeatEvent(time=2.5, beat=1, measure=2, bpm=120.0, confidence=0.9, is_downbeat=True),
        ],
    )


def _transcription() -> BassTranscription:
    return BassTranscription(
        engine="test",
        source_path="audio.wav",
        sample_rate_hz=44100,
        notes=[
            NoteEvent(start=1.0, duration=0.4, midi=40, confidence=0.9, pitch_confidence=0.9, timing_confidence=0.9),
            NoteEvent(start=2.0, duration=0.5, midi=43, confidence=0.9, pitch_confidence=0.9, timing_confidence=0.9),
        ],
    )


def _mapping() -> BassMapping:
    return BassMapping(
        tuning=E_STANDARD,
        max_fret=24,
        notes=[
            MappedNote(start=1.0, duration=0.4, midi=40, string=0, fret=12, source_confidence=0.9, mapping_confidence=0.9),
            MappedNote(start=2.0, duration=0.5, midi=43, string=3, fret=0, source_confidence=0.9, mapping_confidence=0.9),
        ],
    )


def test_xml_matches_core_rocksmith_shape(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path / "project")
    root = build_rocksmith_bass_xml(manifest, _tempo(), _mapping())

    assert root.tag == "song"
    assert root.attrib["version"] == "7"
    assert root.findtext("arrangement") == "Bass"
    assert root.findtext("artistName") == "Test Artist"
    assert root.find("arrangementProperties").attrib["pathBass"] == "1"
    assert root.find("events/event").attrib["code"] == "TS:4/4"

    notes = root.findall("levels/level/notes/note")
    assert len(notes) == 2
    assert notes[0].attrib == {"time": "1.000", "string": "0", "fret": "12", "sustain": "0.400"}
    assert notes[1].attrib["string"] == "3"
    assert notes[1].attrib["fret"] == "0"


def test_drop_d_exports_semitone_offsets() -> None:
    mapping = _mapping().model_copy(update={"tuning": DROP_D})
    assert rocksmith_tuning_offsets(mapping) == (-2, 0, 0, 0, 0, 0)


def test_valid_project_exports_parseable_xml_and_manifest(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _manifest(project)
    write_tempo_map(_tempo(), project / "analysis" / "tempo_map.json")
    write_transcription(_transcription(), project / "analysis" / "bass_raw.json")
    write_bass_mapping(_mapping(), project / "charts" / "bass_mapped.json")

    outputs = export_project_bass_authoring(project)

    assert outputs["xml"].is_file()
    parsed = ET.parse(outputs["xml"]).getroot()
    assert parsed.find("ebeats").attrib["count"] == "5"
    assert parsed.find("levels/level/notes").attrib["count"] == "2"
    assert outputs["manifest"].is_file()
    assert outputs["readme"].is_file()


def test_export_is_blocked_when_validation_fails(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _manifest(project)
    with pytest.raises(PackagingBlockedError):
        export_project_bass_authoring(project)


def test_pinch_harmonic_gets_distinct_xml_attribute_from_natural_harmonic(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path / "project")
    mapping = BassMapping(
        tuning=E_STANDARD,
        max_fret=24,
        notes=[
            MappedNote(
                start=1.0, duration=0.4, midi=40, string=0, fret=12,
                source_confidence=0.9, mapping_confidence=0.9, techniques=["harmonic"],
            ),
            MappedNote(
                start=2.0, duration=0.5, midi=43, string=3, fret=0,
                source_confidence=0.9, mapping_confidence=0.9, techniques=["harmonic_pinch"],
            ),
        ],
    )
    root = build_rocksmith_bass_xml(manifest, _tempo(), mapping)

    notes = root.findall("levels/level/notes/note")
    assert notes[0].attrib.get("harmonic") == "1"
    assert "harmonicPinch" not in notes[0].attrib
    assert notes[1].attrib.get("harmonicPinch") == "1"
    assert "harmonic" not in notes[1].attrib

    properties = root.find("arrangementProperties").attrib
    assert properties["harmonics"] == "1"
    assert properties["pinchHarmonics"] == "1"
