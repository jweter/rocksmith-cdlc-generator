from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from rocksmith_cdlc_generator.guitarpro_import import (
    GuitarProImportError,
    convert_guitarpro_song,
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
        bend=None,
        harmonic=None,
        grace=None,
        trill=None,
        tremoloPicking=None,
        slides=[],
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
    assert out.tuning_midi == [28, 33, 38, 43]
    assert out.notes[0].string_index == 0
    assert out.notes[0].fret == 3
    assert out.notes[0].midi == 31
    assert out.notes[0].duration_seconds == pytest.approx(0.5)
    assert out.notes[0].techniques == ["palm_mute"]
    assert imported.provenance.source_type == "gp5"


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
    guitar = track("Guitar", 29, [string(1, 64)] * 6, [measure(960, [beat(960, 960, [note(1, 0)])])])
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
