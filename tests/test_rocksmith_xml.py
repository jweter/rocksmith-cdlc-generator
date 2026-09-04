from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from rocksmith_cdlc_generator.authoring_export import export_project_bass_authoring
from rocksmith_cdlc_generator.beats import BeatEvent, TempoMap, write_tempo_map
from rocksmith_cdlc_generator.fret_mapping import BassMapping, MappedNote, write_bass_mapping
from rocksmith_cdlc_generator.fretboard import DROP_D, E_STANDARD
from rocksmith_cdlc_generator.models import AudioMetadata, ProjectManifest
from rocksmith_cdlc_generator.packaging_gate import PackagingBlockedError
from rocksmith_cdlc_generator.rocksmith_xml import (
    build_rocksmith_bass_xml,
    note_has_exportable_bend_curve,
    note_has_exportable_slide_target,
    rocksmith_tuning_offsets,
    unsupported_note_techniques,
)
from rocksmith_cdlc_generator.source_import import SourceBendPoint
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


def test_capo_zero_matches_prior_hardcoded_export(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path / "project")
    root = build_rocksmith_bass_xml(manifest, _tempo(), _mapping())
    assert root.findtext("capo") == "0"


def test_capo_tag_reflects_arrangement_capo_value(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path / "project")
    mapping = _mapping().model_copy(update={"capo": 3})
    root = build_rocksmith_bass_xml(manifest, _tempo(), mapping)
    assert root.findtext("capo") == "3"


def test_capo_does_not_offset_individual_bass_note_fret_attributes(tmp_path: Path) -> None:
    """RS2014 represents the capo once via the top-level <capo> tag; individual
    per-note fret attributes are not adjusted (see raynebc/editor-on-fire src/rs.c
    eof_export_rocksmith_2_track(), audited at c0d88eabf7b00b0bd2cac9414df9fa9c6b3e7100)."""

    manifest = _manifest(tmp_path / "project")
    mapping = _mapping().model_copy(update={"capo": 3})
    root = build_rocksmith_bass_xml(manifest, _tempo(), mapping)

    notes = root.findall("levels/level/notes/note")
    assert [note.attrib["fret"] for note in notes] == ["12", "0"]


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


def test_slap_pluck_and_fret_hand_mute_export_real_xml_attributes(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path / "project")
    mapping = BassMapping(
        tuning=E_STANDARD,
        max_fret=24,
        notes=[
            MappedNote(
                start=1.0, duration=0.4, midi=40, string=0, fret=12,
                source_confidence=0.9, mapping_confidence=0.9, techniques=["slap"],
            ),
            MappedNote(
                start=2.0, duration=0.5, midi=43, string=3, fret=0,
                source_confidence=0.9, mapping_confidence=0.9, techniques=["pluck"],
            ),
            MappedNote(
                start=3.0, duration=0.5, midi=43, string=3, fret=2,
                source_confidence=0.9, mapping_confidence=0.9, techniques=["fret_hand_mute"],
            ),
        ],
    )
    root = build_rocksmith_bass_xml(manifest, _tempo(), mapping)

    notes = root.findall("levels/level/notes/note")
    assert notes[0].attrib.get("slap") == "1"
    assert "pluck" not in notes[0].attrib
    assert notes[1].attrib.get("pluck") == "1"
    assert "slap" not in notes[1].attrib
    assert notes[2].attrib.get("mute") == "1"

    assert unsupported_note_techniques(mapping.notes[0]) == []
    assert unsupported_note_techniques(mapping.notes[1]) == []
    assert unsupported_note_techniques(mapping.notes[2]) == []

    properties = root.find("arrangementProperties").attrib
    assert properties["slapPop"] == "1"
    assert properties["fretHandMutes"] == "1"


def test_hammer_on_and_pull_off_export_distinct_xml_attributes_and_set_hopo(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path / "project")
    mapping = BassMapping(
        tuning=E_STANDARD,
        max_fret=24,
        notes=[
            MappedNote(
                start=1.0, duration=0.4, midi=40, string=0, fret=12,
                source_confidence=0.9, mapping_confidence=0.9, techniques=["hammer_on"],
            ),
            MappedNote(
                start=2.0, duration=0.5, midi=43, string=3, fret=0,
                source_confidence=0.9, mapping_confidence=0.9, techniques=["pull_off"],
            ),
        ],
    )
    root = build_rocksmith_bass_xml(manifest, _tempo(), mapping)

    notes = root.findall("levels/level/notes/note")
    assert notes[0].attrib.get("hammerOn") == "1"
    assert "pullOff" not in notes[0].attrib
    assert notes[1].attrib.get("pullOff") == "1"
    assert "hammerOn" not in notes[1].attrib

    properties = root.find("arrangementProperties").attrib
    assert properties["hopo"] == "1"


def test_ambiguous_hammer_pulloff_technique_stays_unsupported_and_omits_hopo(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path / "project")
    note = MappedNote(
        start=1.0, duration=0.4, midi=40, string=0, fret=12,
        source_confidence=0.9, mapping_confidence=0.9, techniques=["hammer_on_pull_off"],
    )
    mapping = BassMapping(tuning=E_STANDARD, max_fret=24, notes=[note])

    assert unsupported_note_techniques(note) == ["hammer_on_pull_off"]

    root = build_rocksmith_bass_xml(manifest, _tempo(), mapping)
    xml_note = root.find("levels/level/notes/note")
    assert "hammerOn" not in xml_note.attrib
    assert "pullOff" not in xml_note.attrib
    assert root.find("arrangementProperties").attrib["hopo"] == "0"


def test_bend_with_curve_data_exports_bend_values(tmp_path: Path) -> None:
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
                source_confidence=0.9,
                mapping_confidence=0.9,
                techniques=["bend"],
                bend_points=[
                    SourceBendPoint(position=0.0, semitones=0.0),
                    SourceBendPoint(position=0.5, semitones=1.0),
                    SourceBendPoint(position=1.0, semitones=1.0),
                ],
            ),
        ],
    )
    root = build_rocksmith_bass_xml(manifest, _tempo(), mapping)

    note = root.find("levels/level/notes/note")
    assert note.attrib.get("bend") == "1"
    bend_values = note.findall("bendValues/bendValue")
    assert [bv.attrib for bv in bend_values] == [
        {"time": "1.000", "step": "0.000"},
        {"time": "1.200", "step": "1.000"},
        {"time": "1.400", "step": "1.000"},
    ]
    assert note.find("bendValues").attrib["count"] == "3"


def test_bend_without_curve_data_stays_unsupported(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path / "project")
    note = MappedNote(
        start=1.0, duration=0.4, midi=40, string=0, fret=12,
        source_confidence=0.9, mapping_confidence=0.9, techniques=["bend"],
    )
    mapping = BassMapping(tuning=E_STANDARD, max_fret=24, notes=[note])

    assert note_has_exportable_bend_curve(note) is False
    assert unsupported_note_techniques(note) == ["bend"]

    root = build_rocksmith_bass_xml(manifest, _tempo(), mapping)
    xml_note = root.find("levels/level/notes/note")
    assert "bend" not in xml_note.attrib
    assert xml_note.find("bendValues") is None


def test_bend_curve_with_point_vibrato_stays_unsupported(tmp_path: Path) -> None:
    """Issue #517: point-level vibrato has no verified Rocksmith encoding yet.

    ``_append_bend_values`` only serializes time/step, so a curve carrying a captured
    ``vibrato`` point must fail closed like any other bend missing lossless detail
    rather than silently dropping the vibrato and claiming a lossless export.
    """

    manifest = _manifest(tmp_path / "project")
    note = MappedNote(
        start=1.0,
        duration=0.4,
        midi=40,
        string=0,
        fret=12,
        source_confidence=0.9,
        mapping_confidence=0.9,
        techniques=["bend"],
        bend_points=[
            SourceBendPoint(position=0.0, semitones=0.0),
            SourceBendPoint(position=1.0, semitones=1.0, vibrato=True),
        ],
    )
    mapping = BassMapping(tuning=E_STANDARD, max_fret=24, notes=[note])

    assert note_has_exportable_bend_curve(note) is False
    assert unsupported_note_techniques(note) == ["bend"]

    root = build_rocksmith_bass_xml(manifest, _tempo(), mapping)
    xml_note = root.find("levels/level/notes/note")
    assert "bend" not in xml_note.attrib
    assert xml_note.find("bendValues") is None
    assert root.find("arrangementProperties").attrib["bends"] == "0"


def test_arrangement_bends_property_is_set_when_an_exportable_curve_is_present(tmp_path: Path) -> None:
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
                source_confidence=0.9,
                mapping_confidence=0.9,
                techniques=["bend"],
                bend_points=[
                    SourceBendPoint(position=0.0, semitones=0.0),
                    SourceBendPoint(position=1.0, semitones=1.0),
                ],
            ),
            MappedNote(start=2.0, duration=0.5, midi=43, string=3, fret=0, source_confidence=0.9, mapping_confidence=0.9),
        ],
    )
    root = build_rocksmith_bass_xml(manifest, _tempo(), mapping)

    assert root.find("arrangementProperties").attrib["bends"] == "1"


def test_slide_with_resolved_target_exports_slide_to_attribute(tmp_path: Path) -> None:
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
                fret=3,
                source_confidence=0.9,
                mapping_confidence=0.9,
                techniques=["slide"],
                slide_target_fret=7,
            ),
        ],
    )
    root = build_rocksmith_bass_xml(manifest, _tempo(), mapping)

    note = root.find("levels/level/notes/note")
    assert note.attrib.get("slideTo") == "7"
    assert root.find("arrangementProperties").attrib["slides"] == "1"


def test_slide_without_resolved_target_stays_unsupported(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path / "project")
    note = MappedNote(
        start=1.0, duration=0.4, midi=40, string=0, fret=3,
        source_confidence=0.9, mapping_confidence=0.9, techniques=["slide"],
    )
    mapping = BassMapping(tuning=E_STANDARD, max_fret=24, notes=[note])

    assert note_has_exportable_slide_target(note) is False
    assert unsupported_note_techniques(note) == ["slide"]

    root = build_rocksmith_bass_xml(manifest, _tempo(), mapping)
    xml_note = root.find("levels/level/notes/note")
    assert "slideTo" not in xml_note.attrib
    assert root.find("arrangementProperties").attrib["slides"] == "0"


def test_legato_slide_with_link_next_exports_link_next_attribute(tmp_path: Path) -> None:
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
                fret=3,
                source_confidence=0.9,
                mapping_confidence=0.9,
                techniques=["slide"],
                slide_target_fret=7,
                link_next=True,
            ),
        ],
    )
    root = build_rocksmith_bass_xml(manifest, _tempo(), mapping)

    note = root.find("levels/level/notes/note")
    assert note.attrib.get("slideTo") == "7"
    assert note.attrib.get("linkNext") == "1"


def test_shift_slide_without_link_next_omits_link_next_attribute(tmp_path: Path) -> None:
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
                fret=3,
                source_confidence=0.9,
                mapping_confidence=0.9,
                techniques=["slide"],
                slide_target_fret=7,
            ),
        ],
    )
    root = build_rocksmith_bass_xml(manifest, _tempo(), mapping)

    note = root.find("levels/level/notes/note")
    assert note.attrib.get("slideTo") == "7"
    assert "linkNext" not in note.attrib


def test_link_next_without_exportable_slide_target_is_never_emitted(tmp_path: Path) -> None:
    # Defensive: link_next should never surface as linkNext="1" unless the concrete
    # slideTo it describes is also being exported (see note_has_exportable_slide_target()).
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
                fret=3,
                source_confidence=0.9,
                mapping_confidence=0.9,
                techniques=["slide"],
                link_next=True,
            ),
        ],
    )
    root = build_rocksmith_bass_xml(manifest, _tempo(), mapping)

    note = root.find("levels/level/notes/note")
    assert "slideTo" not in note.attrib
    assert "linkNext" not in note.attrib
