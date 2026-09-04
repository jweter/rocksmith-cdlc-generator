from pathlib import Path

import pytest

from rocksmith_cdlc_generator.beats import BeatEvent, TempoMap
from rocksmith_cdlc_generator.guitar_authoring import (
    GuitarAuthoringChart,
    GuitarAuthoringNote,
    GuitarChordEvent,
    UnresolvedGuitarNote,
)
from rocksmith_cdlc_generator.models import AudioMetadata, ProjectManifest
from rocksmith_cdlc_generator.rocksmith_xml import (
    build_rocksmith_guitar_xml,
    note_has_exportable_bend_curve,
    rocksmith_guitar_tuning_offsets,
)
from rocksmith_cdlc_generator.source_import import SourceBendPoint, SourceTrustClass


def _manifest(project: Path) -> ProjectManifest:
    project.mkdir(parents=True, exist_ok=True)
    return ProjectManifest(
        project_name="guitar-xml-test",
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


def _note(
    *,
    start: float,
    duration: float,
    midi: int,
    string: int,
    fret: int,
    techniques: list[str] | None = None,
    bend_points: list[SourceBendPoint] | None = None,
    slide_target_fret: int | None = None,
    link_next: bool = False,
) -> GuitarAuthoringNote:
    return GuitarAuthoringNote(
        start_seconds=start,
        duration_seconds=duration,
        midi=midi,
        string_index=string,
        fret=fret,
        techniques=techniques or [],
        bend_points=bend_points or [],
        slide_target_fret=slide_target_fret,
        link_next=link_next,
        trust_class=SourceTrustClass.symbolic_verified,
        review_required=False,
    )


def _lead_chart() -> GuitarAuthoringChart:
    chord_notes = [
        _note(start=2.0, duration=0.5, midi=52, string=0, fret=12, techniques=["palm_mute"]),
        _note(start=2.0, duration=0.5, midi=59, string=1, fret=14),
        _note(start=2.0, duration=0.5, midi=64, string=2, fret=14),
    ]
    return GuitarAuthoringChart(
        arrangement="lead",
        source_sha256="a" * 64,
        alignment_confidence=0.95,
        tuning_midi=(40, 45, 50, 55, 59, 64),
        single_notes=[
            _note(start=1.0, duration=0.25, midi=64, string=5, fret=0, techniques=["vibrato"]),
        ],
        chords=[
            GuitarChordEvent(
                start_seconds=2.0,
                sustain_seconds=0.5,
                chord_id=0,
                shape=(12, 14, 14, -1, -1, -1),
                notes=chord_notes,
            )
        ],
    )


def test_lead_xml_emits_path_tuning_chord_template_and_chord_notes(tmp_path: Path) -> None:
    root = build_rocksmith_guitar_xml(_manifest(tmp_path), _tempo(), _lead_chart())

    assert root.findtext("arrangement") == "Lead"
    props = root.find("arrangementProperties")
    assert props is not None
    assert props.attrib["pathLead"] == "1"
    assert props.attrib["pathRhythm"] == "0"
    assert props.attrib["pathBass"] == "0"
    assert props.attrib["standardTuning"] == "1"
    assert props.attrib["palmMutes"] == "1"
    assert props.attrib["vibrato"] == "1"
    assert props.attrib["bends"] == "0"

    template = root.find("chordTemplates/chordTemplate")
    assert template is not None
    assert template.attrib["fret0"] == "12"
    assert template.attrib["fret1"] == "14"
    assert template.attrib["fret2"] == "14"
    assert template.attrib["fret3"] == "-1"

    chord = root.find("levels/level/chords/chord")
    assert chord is not None
    assert chord.attrib["chordId"] == "0"
    chord_notes = chord.findall("chordNote")
    assert [note.attrib["string"] for note in chord_notes] == ["0", "1", "2"]
    assert chord_notes[0].attrib["palmMute"] == "1"

    note = root.find("levels/level/notes/note")
    assert note is not None
    assert note.attrib["string"] == "5"
    assert note.attrib["vibrato"] == "80"


def test_rhythm_xml_sets_rhythm_path_and_custom_tuning_offsets(tmp_path: Path) -> None:
    chart = _lead_chart().model_copy(
        update={
            "arrangement": "rhythm",
            "tuning_midi": (38, 45, 50, 55, 59, 64),
        }
    )
    root = build_rocksmith_guitar_xml(_manifest(tmp_path), _tempo(), chart)

    assert root.findtext("arrangement") == "Rhythm"
    props = root.find("arrangementProperties")
    assert props is not None
    assert props.attrib["pathLead"] == "0"
    assert props.attrib["pathRhythm"] == "1"
    assert props.attrib["standardTuning"] == "0"
    tuning = root.find("tuning")
    assert tuning is not None
    assert tuning.attrib == {
        "string0": "-2",
        "string1": "0",
        "string2": "0",
        "string3": "0",
        "string4": "0",
        "string5": "0",
    }
    assert rocksmith_guitar_tuning_offsets(chart) == (-2, 0, 0, 0, 0, 0)


def test_guitar_xml_refuses_unresolved_positions(tmp_path: Path) -> None:
    chart = _lead_chart().model_copy(
        update={
            "unresolved_notes": [
                UnresolvedGuitarNote(
                    source_start_seconds=1.25,
                    midi=67,
                    reason="string_fret_unresolved",
                )
            ]
        }
    )

    with pytest.raises(ValueError, match="unresolved"):
        build_rocksmith_guitar_xml(_manifest(tmp_path), _tempo(), chart)


def test_chord_ids_are_reused_without_duplicate_templates(tmp_path: Path) -> None:
    chart = _lead_chart()
    second = chart.chords[0].model_copy(update={"start_seconds": 3.0})
    chart = chart.model_copy(update={"chords": [*chart.chords, second]})

    root = build_rocksmith_guitar_xml(_manifest(tmp_path), _tempo(), chart)

    templates = root.findall("chordTemplates/chordTemplate")
    chords = root.findall("levels/level/chords/chord")
    assert len(templates) == 1
    assert [chord.attrib["chordId"] for chord in chords] == ["0", "0"]


def test_single_note_bend_curve_exports_bend_values(tmp_path: Path) -> None:
    chart = _lead_chart().model_copy(
        update={
            "single_notes": [
                _note(
                    start=1.0,
                    duration=0.5,
                    midi=64,
                    string=5,
                    fret=0,
                    techniques=["bend"],
                    bend_points=[
                        SourceBendPoint(position=0.0, semitones=0.0),
                        SourceBendPoint(position=1.0, semitones=2.0),
                    ],
                ),
            ]
        }
    )

    root = build_rocksmith_guitar_xml(_manifest(tmp_path), _tempo(), chart)

    note = root.find("levels/level/notes/note")
    assert note.attrib["bend"] == "1"
    bend_values = note.findall("bendValues/bendValue")
    assert [bv.attrib for bv in bend_values] == [
        {"time": "1.000", "step": "0.000"},
        {"time": "1.500", "step": "2.000"},
    ]
    assert root.find("arrangementProperties").attrib["bends"] == "1"


def test_bend_curve_with_point_vibrato_stays_unsupported(tmp_path: Path) -> None:
    """Issue #517: a captured point-level vibrato has no verified Rocksmith encoding yet."""

    note = _note(
        start=1.0,
        duration=0.5,
        midi=64,
        string=5,
        fret=0,
        techniques=["bend"],
        bend_points=[
            SourceBendPoint(position=0.0, semitones=0.0),
            SourceBendPoint(position=1.0, semitones=2.0, vibrato=True),
        ],
    )
    assert note_has_exportable_bend_curve(note) is False

    chart = _lead_chart().model_copy(update={"single_notes": [note]})
    root = build_rocksmith_guitar_xml(_manifest(tmp_path), _tempo(), chart)

    xml_note = root.find("levels/level/notes/note")
    assert "bend" not in xml_note.attrib
    assert xml_note.find("bendValues") is None
    assert root.find("arrangementProperties").attrib["bends"] == "0"


def test_chord_note_bend_curve_exports_bend_values(tmp_path: Path) -> None:
    chord_notes = [
        _note(
            start=2.0,
            duration=0.5,
            midi=52,
            string=0,
            fret=12,
            techniques=["bend"],
            bend_points=[SourceBendPoint(position=0.5, semitones=1.0)],
        ),
        _note(start=2.0, duration=0.5, midi=59, string=1, fret=14),
        _note(start=2.0, duration=0.5, midi=64, string=2, fret=14),
    ]
    chart = _lead_chart().model_copy(
        update={
            "chords": [
                GuitarChordEvent(
                    start_seconds=2.0,
                    sustain_seconds=0.5,
                    chord_id=0,
                    shape=(12, 14, 14, -1, -1, -1),
                    notes=chord_notes,
                )
            ]
        }
    )

    root = build_rocksmith_guitar_xml(_manifest(tmp_path), _tempo(), chart)

    chord_note = root.find("levels/level/chords/chord/chordNote")
    assert chord_note.attrib["bend"] == "1"
    bend_value = chord_note.find("bendValues/bendValue")
    assert bend_value.attrib == {"time": "2.250", "step": "1.000"}


def test_single_note_legato_slide_exports_link_next_attribute(tmp_path: Path) -> None:
    chart = _lead_chart().model_copy(
        update={
            "single_notes": [
                _note(
                    start=1.0,
                    duration=0.5,
                    midi=64,
                    string=5,
                    fret=0,
                    techniques=["slide"],
                    slide_target_fret=2,
                    link_next=True,
                ),
            ]
        }
    )

    root = build_rocksmith_guitar_xml(_manifest(tmp_path), _tempo(), chart)

    note = root.find("levels/level/notes/note")
    assert note.attrib["slideTo"] == "2"
    assert note.attrib["linkNext"] == "1"
    assert root.find("arrangementProperties").attrib["slides"] == "1"


def test_single_note_shift_slide_omits_link_next_attribute(tmp_path: Path) -> None:
    chart = _lead_chart().model_copy(
        update={
            "single_notes": [
                _note(
                    start=1.0,
                    duration=0.5,
                    midi=64,
                    string=5,
                    fret=0,
                    techniques=["slide"],
                    slide_target_fret=2,
                ),
            ]
        }
    )

    root = build_rocksmith_guitar_xml(_manifest(tmp_path), _tempo(), chart)

    note = root.find("levels/level/notes/note")
    assert note.attrib["slideTo"] == "2"
    assert "linkNext" not in note.attrib


def test_capo_zero_matches_prior_hardcoded_export(tmp_path: Path) -> None:
    root = build_rocksmith_guitar_xml(_manifest(tmp_path), _tempo(), _lead_chart())
    assert root.findtext("capo") == "0"


def test_capo_tag_reflects_arrangement_capo_value(tmp_path: Path) -> None:
    chart = _lead_chart().model_copy(update={"capo": 2})
    root = build_rocksmith_guitar_xml(_manifest(tmp_path), _tempo(), chart)
    assert root.findtext("capo") == "2"


def test_capo_offsets_chord_template_fret_values_but_not_unused_strings(tmp_path: Path) -> None:
    """raynebc/editor-on-fire src/rs.c eof_export_rocksmith_2_track() (audited at
    c0d88eabf7b00b0bd2cac9414df9fa9c6b3e7100) applies ``fret += tp->capo`` to each
    chord-template string's fret value while leaving an unused string's -1 sentinel
    untouched."""

    chart = _lead_chart().model_copy(update={"capo": 2})
    root = build_rocksmith_guitar_xml(_manifest(tmp_path), _tempo(), chart)

    template = root.find("chordTemplates/chordTemplate")
    assert template.attrib["fret0"] == "14"
    assert template.attrib["fret1"] == "16"
    assert template.attrib["fret2"] == "16"
    assert template.attrib["fret3"] == "-1"
    assert template.attrib["fret4"] == "-1"
    assert template.attrib["fret5"] == "-1"


def test_capo_does_not_offset_individual_note_or_chord_note_fret_attributes(tmp_path: Path) -> None:
    """RS2014 represents the capo once via the top-level <capo> tag; unlike RS1,
    individual per-note/chordNote fret attributes are not adjusted (see
    eof_export_rocksmith_2_track() in the same EOF commit)."""

    chart = _lead_chart().model_copy(update={"capo": 2})
    root = build_rocksmith_guitar_xml(_manifest(tmp_path), _tempo(), chart)

    single_note = root.find("levels/level/notes/note")
    assert single_note.attrib["fret"] == "0"

    chord_note_frets = [
        note.attrib["fret"] for note in root.findall("levels/level/chords/chord/chordNote")
    ]
    assert chord_note_frets == ["12", "14", "14"]


def test_chord_note_legato_slide_exports_link_next_attribute(tmp_path: Path) -> None:
    chord_notes = [
        _note(
            start=2.0,
            duration=0.5,
            midi=52,
            string=0,
            fret=12,
            techniques=["slide"],
            slide_target_fret=14,
            link_next=True,
        ),
        _note(start=2.0, duration=0.5, midi=59, string=1, fret=14),
        _note(start=2.0, duration=0.5, midi=64, string=2, fret=14),
    ]
    chart = _lead_chart().model_copy(
        update={
            "chords": [
                GuitarChordEvent(
                    start_seconds=2.0,
                    sustain_seconds=0.5,
                    chord_id=0,
                    shape=(12, 14, 14, -1, -1, -1),
                    notes=chord_notes,
                )
            ]
        }
    )

    root = build_rocksmith_guitar_xml(_manifest(tmp_path), _tempo(), chart)

    chord_note = root.find("levels/level/chords/chord/chordNote")
    assert chord_note.attrib["slideTo"] == "14"
    assert chord_note.attrib["linkNext"] == "1"
