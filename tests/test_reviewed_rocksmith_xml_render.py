from rocksmith_cdlc_generator.beats import BeatEvent, TempoMap
from rocksmith_cdlc_generator.models import AudioMetadata, ProjectManifest
from rocksmith_cdlc_generator.reviewed_rocksmith_xml import (
    ReviewedRocksmithXmlChord,
    ReviewedRocksmithXmlInput,
    ReviewedRocksmithXmlNote,
)
from rocksmith_cdlc_generator.reviewed_rocksmith_xml_render import (
    build_reviewed_rocksmith_xml,
    reviewed_bass_mapping,
    reviewed_guitar_chart,
)
from rocksmith_cdlc_generator.score_source import ArrangementRole
from rocksmith_cdlc_generator.source_import import SourceBendPoint, SourceTrustClass


def _note(
    index: int,
    *,
    time: float,
    midi: int,
    string: int,
    fret: int,
    techniques: list[str] | None = None,
    bend_points: list[SourceBendPoint] | None = None,
) -> ReviewedRocksmithXmlNote:
    return ReviewedRocksmithXmlNote(
        source_event_index=index,
        time_seconds=time,
        duration_seconds=0.5,
        midi=midi,
        string_index=string,
        fret=fret,
        techniques=(["palm_mute"] if index == 0 else []) if techniques is None else techniques,
        bend_points=bend_points or [],
        import_confidence=0.93,
        trust_class=SourceTrustClass.symbolic_verified,
    )


def _input(role: ArrangementRole, notes, *, chords=None, capo: int = 0) -> ReviewedRocksmithXmlInput:
    tuning = (28, 33, 38, 43) if role is ArrangementRole.bass else (40, 45, 50, 55, 59, 64)
    return ReviewedRocksmithXmlInput(
        role=role,
        source_track_index=2,
        source_output_json=f"analysis/score_fanout/{role.value}.json",
        source_output_sha256="a" * 64,
        recording_sha256="b" * 64,
        score_sha256="c" * 64,
        tuning_midi=tuning,
        capo=capo,
        notes=notes,
        chords=chords or [],
        human_confirmed_timing=True,
    )


def _manifest() -> ProjectManifest:
    return ProjectManifest(
        project_name="reviewed-render-test",
        artist="Test Artist",
        title="Test Song",
        arrangement_instruments=["bass", "lead", "rhythm"],
        source_original_path="private/test.wav",
        source_project_path="source/test.wav",
        source_sha256="d" * 64,
        source_metadata=AudioMetadata(
            duration_seconds=30.0,
            sample_rate_hz=44100,
            channels=2,
            codec_name="pcm_s16le",
            format_name="wav",
        ),
    )


def _tempo_map() -> TempoMap:
    return TempoMap(
        engine="test-reviewed-timing",
        beats=[
            BeatEvent(time=0.5, beat=1, measure=1, bpm=120.0, confidence=1.0, is_downbeat=True),
            BeatEvent(time=1.0, beat=2, measure=1, bpm=120.0, confidence=1.0),
        ],
    )


def test_reviewed_bass_mapping_preserves_reviewed_positions_and_timing():
    xml_input = _input(
        ArrangementRole.bass,
        [_note(0, time=1.25, midi=28, string=0, fret=0)],
    )

    mapping = reviewed_bass_mapping(xml_input)

    assert mapping.tuning.open_midi == (28, 33, 38, 43)
    assert mapping.notes[0].start == 1.25
    assert mapping.notes[0].duration == 0.5
    assert mapping.notes[0].string == 0
    assert mapping.notes[0].fret == 0
    assert mapping.notes[0].position_source == "symbolic"
    assert mapping.notes[0].review_required is False
    assert mapping.notes[0].techniques == ["palm_mute"]


def test_reviewed_guitar_chart_preserves_explicit_chord_membership_without_duplication():
    notes = [
        _note(0, time=1.0, midi=40, string=0, fret=0),
        _note(1, time=1.0, midi=47, string=1, fret=2),
        _note(2, time=2.0, midi=52, string=2, fret=2),
    ]
    chord = ReviewedRocksmithXmlChord(
        source_event_indices=[0, 1],
        time_seconds=1.0,
        sustain_seconds=0.5,
        shape=(0, 2, -1, -1, -1, -1),
        notes=notes[:2],
    )
    xml_input = _input(ArrangementRole.lead, notes, chords=[chord])

    chart = reviewed_guitar_chart(xml_input)

    assert chart.arrangement == "lead"
    assert [(note.string_index, note.fret) for note in chart.single_notes] == [(2, 2)]
    assert len(chart.chords) == 1
    assert chart.chords[0].shape == (0, 2, -1, -1, -1, -1)
    assert [(note.string_index, note.fret) for note in chart.chords[0].notes] == [(0, 0), (1, 2)]
    assert chart.unresolved_notes == []


def test_reviewed_bass_mapping_preserves_capo():
    xml_input = _input(
        ArrangementRole.bass,
        [_note(0, time=1.25, midi=28, string=0, fret=0)],
        capo=2,
    )

    mapping = reviewed_bass_mapping(xml_input)

    assert mapping.capo == 2


def test_reviewed_guitar_chart_preserves_capo():
    notes = [_note(0, time=1.0, midi=40, string=0, fret=0)]
    xml_input = _input(ArrangementRole.lead, notes, capo=2)

    chart = reviewed_guitar_chart(xml_input)

    assert chart.capo == 2


def test_reviewed_guitar_handoff_renders_capo_tag_and_offsets_chord_template():
    notes = [
        _note(0, time=1.0, midi=40, string=0, fret=0),
        _note(1, time=1.0, midi=47, string=1, fret=2),
        _note(2, time=2.0, midi=52, string=2, fret=2),
    ]
    chord = ReviewedRocksmithXmlChord(
        source_event_indices=[0, 1],
        time_seconds=1.0,
        sustain_seconds=0.5,
        shape=(0, 2, -1, -1, -1, -1),
        notes=notes[:2],
    )

    root = build_reviewed_rocksmith_xml(
        _manifest(),
        _tempo_map(),
        _input(ArrangementRole.rhythm, notes, chords=[chord], capo=2),
    )

    assert root.findtext("capo") == "2"
    template = root.find("chordTemplates/chordTemplate")
    assert template.attrib["fret0"] == "2"
    assert template.attrib["fret1"] == "4"
    assert template.attrib["fret2"] == "-1"
    note = root.find("levels/level/notes/note")
    assert note.attrib["fret"] == "2"


def test_reviewed_guitar_handoff_renders_with_existing_xml_builder():
    notes = [
        _note(0, time=1.0, midi=40, string=0, fret=0),
        _note(1, time=1.0, midi=47, string=1, fret=2),
        _note(2, time=2.0, midi=52, string=2, fret=2),
    ]
    chord = ReviewedRocksmithXmlChord(
        source_event_indices=[0, 1],
        time_seconds=1.0,
        sustain_seconds=0.5,
        shape=(0, 2, -1, -1, -1, -1),
        notes=notes[:2],
    )

    root = build_reviewed_rocksmith_xml(
        _manifest(),
        _tempo_map(),
        _input(ArrangementRole.rhythm, notes, chords=[chord]),
    )

    assert root.findtext("arrangement") == "Rhythm"
    assert root.find("chordTemplates").attrib["count"] == "1"
    level = root.find("levels/level")
    assert level is not None
    assert level.find("notes").attrib["count"] == "1"
    assert level.find("chords").attrib["count"] == "1"


def test_reviewed_bass_handoff_renders_bend_curve_end_to_end():
    points = [
        SourceBendPoint(position=0.0, semitones=0.0),
        SourceBendPoint(position=1.0, semitones=1.0),
    ]
    notes = [
        _note(0, time=1.25, midi=28, string=0, fret=2, techniques=["bend"], bend_points=points),
    ]

    root = build_reviewed_rocksmith_xml(
        _manifest(),
        _tempo_map(),
        _input(ArrangementRole.bass, notes),
    )

    note = root.find("levels/level/notes/note")
    assert note.attrib["bend"] == "1"
    bend_values = note.findall("bendValues/bendValue")
    assert [bv.attrib for bv in bend_values] == [
        {"time": "1.250", "step": "0.000"},
        {"time": "1.750", "step": "1.000"},
    ]
