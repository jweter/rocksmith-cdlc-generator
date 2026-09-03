from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from rocksmith_cdlc_generator.guitarpro_import import (
    GuitarProImportError,
    convert_guitarpro_song,
    select_arrangement_track,
    select_bass_track,
)


def string(number: int, value: int):
    return NS(number=number, value=value)


def note(string_no: int, fret: int, **effect_flags):
    effect = NS(
        hammer=effect_flags.get("hammer", False),
        palmMute=effect_flags.get("palmMute", False),
        staccato=False,
        letRing=False,
        vibrato=effect_flags.get("vibrato", False),
        ghostNote=False,
        accentuatedNote=False,
        heavyAccentuatedNote=False,
        bend=effect_flags.get("bend"),
        harmonic=effect_flags.get("harmonic"),
        grace=None,
        trill=None,
        tremoloPicking=None,
        slides=effect_flags.get("slides", []),
    )
    return NS(string=string_no, value=fret, effect=effect, type=NS(name="normal"))


def beat(start: int, duration: int, notes, tempo=None):
    mix = NS(tempo=NS(value=tempo)) if tempo is not None else None
    return NS(start=start, duration=NS(time=duration), notes=notes, effect=NS(mixTableChange=mix))


def measure(start: int, beats, numerator=4, denominator=4):
    header = NS(
        start=start,
        timeSignature=NS(numerator=numerator, denominator=NS(value=denominator)),
    )
    return NS(header=header, voices=[NS(beats=beats), NS(beats=[])])


def track(name: str, program: int, strings, measures):
    return NS(name=name, channel=NS(channel=0, instrument=program), strings=strings, measures=measures)


def song(tracks, tempo=120, repeat=False):
    return NS(
        tracks=tracks,
        tempo=tempo,
        measureHeaders=[NS(isRepeatOpen=repeat, repeatClose=0)],
    )


def standard_guitar_strings():
    return [
        string(1, 64),
        string(2, 59),
        string(3, 55),
        string(4, 50),
        string(5, 45),
        string(6, 40),
    ]


def test_gp_import_preserves_bass_tuning_string_fret_and_pitch():
    bass = track(
        "Bass",
        33,
        [string(1, 43), string(2, 38), string(3, 33), string(4, 28)],
        [measure(960, [beat(960, 960, [note(4, 3, palmMute=True)])])],
    )
    imported = convert_guitarpro_song(
        song([bass]),
        source_path=Path("fixture.gp5"),
        source_sha256="a" * 64,
        importer_version="0.11",
    )
    out = imported.tracks[0]
    assert out.instrument == "bass"
    assert out.tuning_midi == [28, 33, 38, 43]
    assert out.notes[0].string_index == 0
    assert out.notes[0].fret == 3
    assert out.notes[0].midi == 31
    assert out.notes[0].duration_seconds == pytest.approx(0.5)
    assert out.notes[0].techniques == ["palm_mute"]
    assert imported.provenance.source_type == "gp5"


def test_gp_import_preserves_lead_guitar_six_string_tuning_and_polyphony():
    lead = track(
        "Lead Guitar",
        29,
        standard_guitar_strings(),
        [measure(960, [beat(960, 960, [note(6, 3), note(5, 5), note(1, 8, vibrato=True)])])],
    )
    imported = convert_guitarpro_song(
        song([lead]),
        source_path=Path("lead.gp5"),
        source_sha256="d" * 64,
        instrument="lead",
    )
    out = imported.tracks[0]
    assert out.instrument == "lead"
    assert out.tuning_midi == [40, 45, 50, 55, 59, 64]
    assert [(n.string_index, n.fret, n.midi) for n in out.notes] == [
        (0, 3, 43),
        (1, 5, 50),
        (5, 8, 72),
    ]
    assert out.notes[-1].techniques == ["vibrato"]
    assert not any("6 strings" in warning for warning in imported.warnings)


def test_gp_import_selects_named_lead_and_rhythm_tracks():
    strings = standard_guitar_strings()
    bass = track("Bass", 33, [string(1, 43), string(2, 38), string(3, 33), string(4, 28)], [measure(960, [beat(960, 960, [note(4, 0)])])])
    rhythm = track("Rhythm Guitar", 27, strings, [measure(960, [beat(960, 960, [note(6, 0)])])])
    lead = track("Lead Guitar", 29, strings, [measure(960, [beat(960, 960, [note(6, 3)])])])
    fixture = song([bass, rhythm, lead])

    lead_index, lead_selected = select_arrangement_track(fixture, instrument="lead")
    rhythm_index, rhythm_selected = select_arrangement_track(fixture, instrument="rhythm")
    assert (lead_index, lead_selected) == (2, lead)
    assert (rhythm_index, rhythm_selected) == (1, rhythm)


def test_gp_import_does_not_auto_select_bass_as_guitar():
    bass = track(
        "Six String Bass",
        33,
        [string(1, 52), string(2, 47), string(3, 43), string(4, 38), string(5, 33), string(6, 28)],
        [measure(960, [beat(960, 960, [note(6, 0)])])],
    )
    with pytest.raises(GuitarProImportError, match="No credible Lead"):
        select_arrangement_track(song([bass]), instrument="lead")


def test_gp_import_applies_tempo_change_to_absolute_time():
    bass = track(
        "Bass",
        33,
        [string(1, 43), string(2, 38), string(3, 33), string(4, 28)],
        [measure(960, [
            beat(960, 960, [note(4, 0)]),
            beat(1920, 960, [note(4, 2)], tempo=60),
            beat(2880, 960, [note(4, 3)]),
        ])],
    )
    imported = convert_guitarpro_song(song([bass], tempo=120), source_path=Path("tempo.gp5"), source_sha256="b" * 64)
    notes = imported.tracks[0].notes
    assert notes[0].start_seconds == pytest.approx(0.0)
    assert notes[1].start_seconds == pytest.approx(0.5)
    assert notes[2].start_seconds == pytest.approx(1.5)
    assert [event.bpm for event in imported.tempo_events] == [120.0, 60.0]


def test_gp_import_selects_named_bass_track():
    guitar = track("Guitar", 29, standard_guitar_strings(), [measure(960, [beat(960, 960, [note(1, 0)])])])
    bass = track("Picked Bass", 34, [string(1, 43), string(2, 38), string(3, 33), string(4, 28)], [measure(960, [beat(960, 960, [note(4, 0)])])])
    index, selected = select_bass_track(song([guitar, bass]))
    assert index == 1
    assert selected is bass


def test_gp_import_refuses_ambiguous_bass_tracks():
    strings = [string(1, 43), string(2, 38), string(3, 33), string(4, 28)]
    a = track("Bass A", 33, strings, [measure(960, [beat(960, 960, [note(4, 0)])])])
    b = track("Bass B", 33, strings, [measure(960, [beat(960, 960, [note(4, 0)])])])
    with pytest.raises(GuitarProImportError, match="ambiguous"):
        select_bass_track(song([a, b]))
    index, selected = select_bass_track(song([a, b]), track_index=1)
    assert index == 1
    assert selected is b


def test_gp_import_flags_repeat_and_non_four_string_sources():
    strings = [string(1, 47), string(2, 43), string(3, 38), string(4, 33), string(5, 28)]
    bass = track("5-string Bass", 33, strings, [measure(960, [beat(960, 960, [note(5, 0)])])])
    imported = convert_guitarpro_song(song([bass], repeat=True), source_path=Path("five.gp5"), source_sha256="c" * 64)
    assert any("5 strings" in warning for warning in imported.warnings)
    assert any("repeat structure" in warning for warning in imported.warnings)


def _slide(*names):
    return [NS(name=name) for name in names]


def test_gp_import_preserves_shift_slide_kind_alongside_generic_slide_flag():
    bass = track(
        "Bass",
        33,
        [string(1, 43), string(2, 38), string(3, 33), string(4, 28)],
        [measure(960, [beat(960, 960, [note(4, 3, slides=_slide("shiftSlideTo"))])])],
    )
    imported = convert_guitarpro_song(song([bass]), source_path=Path("fixture.gp5"), source_sha256="a" * 64)
    note_event = imported.tracks[0].notes[0]

    assert "slide" in note_event.techniques
    assert note_event.slide_kinds == ["shift"]


def test_gp_import_preserves_multiple_distinct_slide_kinds():
    bass = track(
        "Bass",
        33,
        [string(1, 43), string(2, 38), string(3, 33), string(4, 28)],
        [measure(960, [beat(960, 960, [note(4, 3, slides=_slide("intoFromBelow", "legatoSlideTo"))])])],
    )
    imported = convert_guitarpro_song(song([bass]), source_path=Path("fixture.gp5"), source_sha256="a" * 64)
    note_event = imported.tracks[0].notes[0]

    assert note_event.slide_kinds == ["into_from_below", "legato"]


def test_gp_import_note_without_slide_has_no_slide_kinds():
    bass = track(
        "Bass",
        33,
        [string(1, 43), string(2, 38), string(3, 33), string(4, 28)],
        [measure(960, [beat(960, 960, [note(4, 3)])])],
    )
    imported = convert_guitarpro_song(song([bass]), source_path=Path("fixture.gp5"), source_sha256="a" * 64)
    note_event = imported.tracks[0].notes[0]
    assert "slide" not in note_event.techniques
    assert note_event.slide_kinds == []


def test_gp_import_resolves_shift_slide_target_from_next_same_string_note():
    bass = track(
        "Bass",
        33,
        [string(1, 43), string(2, 38), string(3, 33), string(4, 28)],
        [measure(960, [
            beat(960, 480, [note(4, 3, slides=_slide("shiftSlideTo"))]),
            beat(1440, 480, [note(4, 7)]),
        ])],
    )
    imported = convert_guitarpro_song(song([bass]), source_path=Path("fixture.gp5"), source_sha256="a" * 64)
    slid_note, target_note = imported.tracks[0].notes
    assert slid_note.slide_target_fret == 7
    assert target_note.slide_target_fret is None


def test_gp_import_resolves_legato_slide_target_across_an_unrelated_string():
    bass = track(
        "Bass",
        33,
        [string(1, 43), string(2, 38), string(3, 33), string(4, 28)],
        [measure(960, [
            beat(960, 480, [note(4, 3, slides=_slide("legatoSlideTo")), note(2, 0)]),
            beat(1440, 480, [note(4, 5)]),
        ])],
    )
    imported = convert_guitarpro_song(song([bass]), source_path=Path("fixture.gp5"), source_sha256="a" * 64)
    slid_note = next(n for n in imported.tracks[0].notes if "slide" in n.techniques)
    # The intervening note on a different string must not be mistaken for the slide target.
    assert slid_note.slide_target_fret == 5


def test_gp_import_leaves_slide_target_unresolved_without_a_later_same_string_note():
    bass = track(
        "Bass",
        33,
        [string(1, 43), string(2, 38), string(3, 33), string(4, 28)],
        [measure(960, [beat(960, 960, [note(4, 3, slides=_slide("shiftSlideTo"))])])],
    )
    imported = convert_guitarpro_song(song([bass]), source_path=Path("fixture.gp5"), source_sha256="a" * 64)
    note_event = imported.tracks[0].notes[0]
    assert note_event.slide_target_fret is None


def test_gp_import_leaves_slide_target_unresolved_for_target_less_slide_kinds():
    bass = track(
        "Bass",
        33,
        [string(1, 43), string(2, 38), string(3, 33), string(4, 28)],
        [measure(960, [
            beat(960, 480, [note(4, 3, slides=_slide("outDownwards"))]),
            beat(1440, 480, [note(4, 7)]),
        ])],
    )
    imported = convert_guitarpro_song(song([bass]), source_path=Path("fixture.gp5"), source_sha256="a" * 64)
    slid_note, _ = imported.tracks[0].notes
    assert slid_note.slide_kinds == ["out_downwards"]
    assert slid_note.slide_target_fret is None


def _bend_effect(points):
    return NS(points=[NS(position=position, value=value, vibrato=vibrato) for position, value, vibrato in points])


def test_gp_import_preserves_bend_curve_instead_of_discarding_it():
    # A bend from 0 to 2 semitones at the midpoint, released back to 0 by the note's end.
    bend = _bend_effect([(0, 0, False), (6, 2, False), (12, 0, True)])
    bass = track(
        "Bass",
        33,
        [string(1, 43), string(2, 38), string(3, 33), string(4, 28)],
        [measure(960, [beat(960, 960, [note(4, 3, bend=bend)])])],
    )
    imported = convert_guitarpro_song(song([bass]), source_path=Path("fixture.gp5"), source_sha256="a" * 64)
    note_event = imported.tracks[0].notes[0]

    assert "bend" in note_event.techniques
    assert [(point.position, point.semitones, point.vibrato) for point in note_event.bend_points] == [
        (0.0, 0.0, False),
        (0.5, 2.0, False),
        (1.0, 0.0, True),
    ]


def test_gp_import_note_without_bend_has_no_bend_points():
    bass = track(
        "Bass",
        33,
        [string(1, 43), string(2, 38), string(3, 33), string(4, 28)],
        [measure(960, [beat(960, 960, [note(4, 3)])])],
    )
    imported = convert_guitarpro_song(song([bass]), source_path=Path("fixture.gp5"), source_sha256="a" * 64)
    note_event = imported.tracks[0].notes[0]
    assert "bend" not in note_event.techniques
    assert note_event.bend_points == []


def _harmonic(type_value: int):
    return NS(type=type_value)


def _harmonic_bass_note(harmonic_type: int):
    bass = track(
        "Bass",
        33,
        [string(1, 43), string(2, 38), string(3, 33), string(4, 28)],
        [measure(960, [beat(960, 960, [note(4, 3, harmonic=_harmonic(harmonic_type))])])],
    )
    imported = convert_guitarpro_song(song([bass]), source_path=Path("fixture.gp5"), source_sha256="a" * 64)
    return imported.tracks[0].notes[0]


def test_gp_import_natural_harmonic_keeps_generic_harmonic_label():
    note_event = _harmonic_bass_note(1)  # NaturalHarmonic
    assert note_event.techniques == ["harmonic"]


@pytest.mark.parametrize("harmonic_type", [2, 3, 4, 5])  # Artificial, Tapped, Pinch, Semi
def test_gp_import_non_natural_harmonics_get_pinch_label(harmonic_type):
    note_event = _harmonic_bass_note(harmonic_type)
    assert note_event.techniques == ["harmonic_pinch"]
