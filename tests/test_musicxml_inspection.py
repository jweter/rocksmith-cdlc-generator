from __future__ import annotations

from pathlib import Path

from rocksmith_cdlc_generator.musicxml_inspection import inspect_musicxml_source


SCORE = """<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="4.0">
  <part-list>
    <score-part id="P1">
      <part-name>E.Guitar</part-name>
      <midi-instrument id="P1-I1"><midi-program>29</midi-program></midi-instrument>
    </score-part>
    <score-part id="P2">
      <part-name>E.Bass</part-name>
      <midi-instrument id="P2-I1"><midi-program>34</midi-program></midi-instrument>
    </score-part>
  </part-list>
  <part id="P1">
    <measure number="1">
      <attributes>
        <divisions>4</divisions>
        <staff-details>
          <staff-lines>6</staff-lines>
          <staff-tuning line="1"><tuning-step>E</tuning-step><tuning-octave>2</tuning-octave></staff-tuning>
          <staff-tuning line="2"><tuning-step>A</tuning-step><tuning-octave>2</tuning-octave></staff-tuning>
          <staff-tuning line="3"><tuning-step>D</tuning-step><tuning-octave>3</tuning-octave></staff-tuning>
          <staff-tuning line="4"><tuning-step>G</tuning-step><tuning-octave>3</tuning-octave></staff-tuning>
          <staff-tuning line="5"><tuning-step>B</tuning-step><tuning-octave>3</tuning-octave></staff-tuning>
          <staff-tuning line="6"><tuning-step>E</tuning-step><tuning-octave>4</tuning-octave></staff-tuning>
        </staff-details>
      </attributes>
      <note><pitch><step>E</step><octave>4</octave></pitch><duration>4</duration></note>
      <note><rest/><duration>4</duration></note>
    </measure>
  </part>
  <part id="P2">
    <measure number="1">
      <attributes>
        <divisions>4</divisions>
        <staff-details>
          <staff-lines>4</staff-lines>
          <staff-tuning line="1"><tuning-step>E</tuning-step><tuning-octave>1</tuning-octave></staff-tuning>
          <staff-tuning line="2"><tuning-step>A</tuning-step><tuning-octave>1</tuning-octave></staff-tuning>
          <staff-tuning line="3"><tuning-step>D</tuning-step><tuning-octave>2</tuning-octave></staff-tuning>
          <staff-tuning line="4"><tuning-step>G</tuning-step><tuning-octave>2</tuning-octave></staff-tuning>
        </staff-details>
      </attributes>
      <note><pitch><step>E</step><octave>2</octave></pitch><duration>4</duration></note>
      <note><pitch><step>G</step><octave>2</octave></pitch><duration>4</duration></note>
    </measure>
  </part>
</score-partwise>
"""


def _write_score(tmp_path: Path) -> Path:
    path = tmp_path / "guitar-pro-export.musicxml"
    path.write_text(SCORE, encoding="utf-8")
    return path


def test_inspection_lists_parts_in_source_order(tmp_path: Path) -> None:
    report = inspect_musicxml_source(_write_score(tmp_path))

    assert [part.part_index for part in report.parts] == [0, 1]
    assert [part.name for part in report.parts] == ["E.Guitar", "E.Bass"]
    assert report.parts[0].pitched_note_count == 1
    assert report.parts[0].rest_count == 1
    assert report.parts[1].pitched_note_count == 2


def test_inspection_preserves_tuning_and_role_scores(tmp_path: Path) -> None:
    report = inspect_musicxml_source(_write_score(tmp_path))
    guitar, bass = report.parts

    assert guitar.tuning_midi == [40, 45, 50, 55, 59, 64]
    assert bass.tuning_midi == [28, 33, 38, 43]
    assert guitar.lead_score > 0
    assert guitar.rhythm_score > 0
    assert bass.bass_score > guitar.bass_score
    assert bass.lead_score < 0
    assert bass.rhythm_score < 0


def test_inspection_rejects_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing.musicxml"
    try:
        inspect_musicxml_source(missing)
    except FileNotFoundError as exc:
        assert "MusicXML file not found" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected FileNotFoundError")
