from pathlib import Path

import pytest

from rocksmith_cdlc_generator.psarc_import import (
    PsarcImportError,
    _note_techniques,
    convert_rocksmith_bass_xml,
)
from rocksmith_cdlc_generator.source_import import SourceTrustClass
from xml.etree import ElementTree as ET


def _write_bass_xml(path: Path, *, arrangement: str = "Bass") -> Path:
    path.write_text(
        f'''<?xml version="1.0" encoding="utf-8"?>
<song version="7">
  <arrangement>{arrangement}</arrangement>
  <tuning string0="-2" string1="0" string2="0" string3="0" string4="0" string5="0" />
  <events count="1"><event time="0.000" code="TS:4/4" /></events>
  <ebeats count="5">
    <ebeat time="0.250" measure="1" />
    <ebeat time="0.750" />
    <ebeat time="1.250" />
    <ebeat time="1.750" />
    <ebeat time="2.250" measure="2" />
  </ebeats>
  <levels count="2">
    <level difficulty="0">
      <notes count="1"><note time="0.750" string="0" fret="2" sustain="0.100" /></notes>
      <chords count="0" />
    </level>
    <level difficulty="3">
      <notes count="2">
        <note time="0.750" string="0" fret="2" sustain="0.400" palmMute="1" accent="1" />
        <note time="1.250" string="1" fret="3" sustain="0.250" vibrato="80" slideTo="5" />
      </notes>
      <chords count="1"><chord time="1.750" chordId="0" /></chords>
    </level>
  </levels>
</song>
''',
        encoding="utf-8",
    )
    return path


def test_converts_extracted_bass_xml_to_neutral_source(tmp_path: Path) -> None:
    xml = _write_bass_xml(tmp_path / "arr_bass_RS2.xml")
    psarc = tmp_path / "song_p.psarc"
    imported = convert_rocksmith_bass_xml(
        xml,
        source_path=psarc,
        source_sha256="a" * 64,
        importer_version="test-commit",
    )

    assert imported.provenance.source_type == "rocksmith_psarc"
    assert imported.provenance.source_filename == "song_p.psarc"
    assert imported.provenance.importer_version == "test-commit"
    assert imported.beat_times_seconds == [0.25, 0.75, 1.25, 1.75, 2.25]
    assert imported.tempo_events[0].time_seconds == 0.0
    assert imported.tempo_events[0].bpm == pytest.approx(120.0)
    assert imported.time_signatures[0].numerator == 4
    assert imported.time_signatures[0].denominator == 4

    track = imported.tracks[0]
    assert track.instrument == "bass"
    assert track.tuning_midi == [26, 33, 38, 43]
    assert len(track.notes) == 2
    assert track.notes[0].midi == 28
    assert track.notes[0].string_index == 0
    assert track.notes[0].fret == 2
    assert track.notes[0].techniques == ["accent", "palm_mute"]
    assert track.notes[0].trust_class == SourceTrustClass.symbolic_unverified
    assert track.notes[1].midi == 36
    assert track.notes[1].techniques == ["slide", "vibrato"]
    assert any("chord" in warning.lower() for warning in imported.warnings)
    assert any("difficulty level 3" in warning for warning in imported.warnings)


def _note(**attrib: str) -> ET.Element:
    return ET.Element("note", attrib)


def test_slap_and_pluck_require_the_played_value_not_just_applicability() -> None:
    # Rocksmith 2014 XML's slap/pluck attributes are ternary: -1 means not applicable to
    # this arrangement, 0 means applicable but this specific note was not slapped/plucked,
    # and only 1 marks an actual slap/pluck articulation. A bass note explicitly marked "not
    # slapped" (0) must not be reported as carrying the "slap" technique.
    assert _note_techniques(_note(slap="-1", pluck="-1")) == []
    assert _note_techniques(_note(slap="0", pluck="0")) == []
    assert _note_techniques(_note(slap="1", pluck="0")) == ["slap"]
    assert _note_techniques(_note(slap="0", pluck="1")) == ["pluck"]


def test_pinch_harmonic_and_fret_hand_mute_use_canonical_technique_labels() -> None:
    # harmonicPinch="1" and mute="1" must round-trip using the same technique labels this
    # project's reviewed-authority pipeline already recognizes (reviewed_techniques.
    # SUPPORTED_TECHNIQUES, rocksmith_xml.DIRECT_NOTE_TECHNIQUES) -- not a mismatched
    # synonym that would silently fail to re-export or be rejected on human review.
    assert _note_techniques(_note(harmonicPinch="1")) == ["harmonic_pinch"]
    assert _note_techniques(_note(mute="1")) == ["fret_hand_mute"]


def test_rejects_non_bass_rocksmith_xml(tmp_path: Path) -> None:
    xml = _write_bass_xml(tmp_path / "arr_lead_RS2.xml", arrangement="Lead")
    with pytest.raises(PsarcImportError, match="Expected a Bass arrangement"):
        convert_rocksmith_bass_xml(
            xml,
            source_path=tmp_path / "song.psarc",
            source_sha256="b" * 64,
        )


def test_rejects_invalid_explicit_beat_grid(tmp_path: Path) -> None:
    xml = _write_bass_xml(tmp_path / "arr_bass_RS2.xml")
    text = xml.read_text(encoding="utf-8").replace('<ebeat time="1.250" />', '<ebeat time="0.700" />')
    xml.write_text(text, encoding="utf-8")
    with pytest.raises(PsarcImportError, match="strictly increasing"):
        convert_rocksmith_bass_xml(
            xml,
            source_path=tmp_path / "song.psarc",
            source_sha256="c" * 64,
        )
