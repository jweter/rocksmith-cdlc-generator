from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

import pytest

from rocksmith_cdlc_generator.musicxml_import import import_musicxml, import_project_musicxml
from rocksmith_cdlc_generator.source_import import ImportedSource, SourceTrustClass


BASS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="4.0">
  <part-list>
    <score-part id="P1"><part-name>Drums</part-name><midi-instrument id="P1-I1"><midi-program>1</midi-program></midi-instrument></score-part>
    <score-part id="P2"><part-name>Electric Bass</part-name><midi-instrument id="P2-I1"><midi-program>34</midi-program></midi-instrument></score-part>
  </part-list>
  <part id="P1">
    <measure number="1"><attributes><divisions>4</divisions><time><beats>4</beats><beat-type>4</beat-type></time></attributes><note><pitch><step>C</step><octave>4</octave></pitch><duration>4</duration></note></measure>
  </part>
  <part id="P2">
    <measure number="1">
      <attributes>
        <divisions>4</divisions><time><beats>4</beats><beat-type>4</beat-type></time>
        <staff-details>
          <staff-tuning line="1"><tuning-step>E</tuning-step><tuning-octave>1</tuning-octave></staff-tuning>
          <staff-tuning line="2"><tuning-step>A</tuning-step><tuning-octave>1</tuning-octave></staff-tuning>
          <staff-tuning line="3"><tuning-step>D</tuning-step><tuning-octave>2</tuning-octave></staff-tuning>
          <staff-tuning line="4"><tuning-step>G</tuning-step><tuning-octave>2</tuning-octave></staff-tuning>
        </staff-details>
      </attributes>
      <direction><sound tempo="120"/></direction>
      <note>
        <pitch><step>G</step><octave>1</octave></pitch><duration>4</duration>
        <notations><technical><string>4</string><fret>3</fret><hammer-on type="start">H</hammer-on></technical></notations>
      </note>
      <note><pitch><step>A</step><octave>1</octave></pitch><duration>4</duration><tie type="start"/><notations><technical><string>3</string><fret>0</fret></technical></notations></note>
      <direction><sound tempo="60"/></direction>
      <note><pitch><step>B</step><octave>1</octave></pitch><duration>4</duration><notations><technical><string>3</string><fret>2</fret></technical></notations></note>
    </measure>
  </part>
</score-partwise>
"""


def test_import_musicxml_selects_bass_and_preserves_tab_and_tempo(tmp_path: Path) -> None:
    path = tmp_path / "song.musicxml"
    path.write_text(BASS_XML, encoding="utf-8")
    imported = import_musicxml(path)
    track = imported.tracks[0]
    assert track.name == "Electric Bass"
    assert track.tuning_midi == [28, 33, 38, 43]
    assert track.program_numbers == [34]
    assert [note.midi for note in track.notes] == [31, 33, 35]
    assert [(note.string_index, note.fret) for note in track.notes] == [(0, 3), (1, 0), (1, 2)]
    assert "hammer_on" in track.notes[0].techniques
    assert "tie_start" in track.notes[1].techniques
    assert all(note.trust_class == SourceTrustClass.symbolic_unverified for note in track.notes)
    assert [round(note.start_seconds, 3) for note in track.notes] == [0.0, 0.5, 1.0]
    assert [round(note.duration_seconds, 3) for note in track.notes] == [0.5, 0.5, 1.0]
    assert [event.bpm for event in imported.tempo_events] == [120.0, 60.0]
    assert imported.time_signatures[0].numerator == 4
    assert imported.time_signatures[0].denominator == 4


def test_musicxml_part_selection_refuses_ambiguous_bass_parts(tmp_path: Path) -> None:
    xml = """<score-partwise version="4.0"><part-list>
    <score-part id="P1"><part-name>Bass A</part-name><midi-instrument id="a"><midi-program>34</midi-program></midi-instrument></score-part>
    <score-part id="P2"><part-name>Bass B</part-name><midi-instrument id="b"><midi-program>34</midi-program></midi-instrument></score-part>
    </part-list>
    <part id="P1"><measure number="1"><attributes><divisions>1</divisions></attributes><note><pitch><step>E</step><octave>1</octave></pitch><duration>1</duration></note></measure></part>
    <part id="P2"><measure number="1"><attributes><divisions>1</divisions></attributes><note><pitch><step>A</step><octave>1</octave></pitch><duration>1</duration></note></measure></part>
    </score-partwise>"""
    path = tmp_path / "ambiguous.xml"
    path.write_text(xml, encoding="utf-8")
    with pytest.raises(ValueError, match="ambiguous"):
        import_musicxml(path)
    imported = import_musicxml(path, part_index=1)
    assert imported.tracks[0].source_track_index == 1


def test_import_project_musicxml_writes_neutral_artifact(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    path = tmp_path / "song.musicxml"
    path.write_text(BASS_XML, encoding="utf-8")
    output = import_project_musicxml(project, path)
    loaded = ImportedSource.read_json(output)
    assert output.parent == project / "sources" / "imported"
    assert loaded.provenance.source_type == "musicxml"
    assert loaded.provenance.source_filename == "song.musicxml"
    assert len(loaded.provenance.source_sha256) == 64
    assert loaded.tracks[0].notes[0].fret == 3


def test_import_compressed_mxl(tmp_path: Path) -> None:
    path = tmp_path / "song.mxl"
    container = """<?xml version="1.0"?><container><rootfiles><rootfile full-path="score.musicxml"/></rootfiles></container>"""
    with ZipFile(path, "w") as archive:
        archive.writestr("META-INF/container.xml", container)
        archive.writestr("score.musicxml", BASS_XML)
    imported = import_musicxml(path)
    assert imported.provenance.source_filename == "song.mxl"
    assert imported.tracks[0].tuning_midi == [28, 33, 38, 43]


def test_missing_tempo_is_explicit_warning(tmp_path: Path) -> None:
    path = tmp_path / "no-tempo.xml"
    path.write_text(BASS_XML.replace('<direction><sound tempo="120"/></direction>', "").replace('<direction><sound tempo="60"/></direction>', ""), encoding="utf-8")
    imported = import_musicxml(path)
    assert any("assumes 120 BPM" in warning for warning in imported.warnings)
    assert imported.tempo_events[0].bpm == 120.0


def test_repeats_are_flagged_not_silently_expanded(tmp_path: Path) -> None:
    xml = BASS_XML.replace('<measure number="1">', '<measure number="1"><barline location="left"><repeat direction="forward"/></barline>', 2)
    path = tmp_path / "repeat.musicxml"
    path.write_text(xml, encoding="utf-8")
    imported = import_musicxml(path)
    assert any("repeat structures" in warning for warning in imported.warnings)
