from __future__ import annotations

import json
from pathlib import Path

import pytest

from rocksmith_cdlc_generator.musicxml_multi_import import (
    MusicXMLArrangementSelection,
    import_project_musicxml_arrangements,
)


MUSICXML = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<score-partwise version=\"4.0\">
  <part-list>
    <score-part id=\"P1\"><part-name>Lead Guitar</part-name><midi-instrument id=\"P1-I1\"><midi-program>30</midi-program></midi-instrument></score-part>
    <score-part id=\"P2\"><part-name>Rhythm Guitar</part-name><midi-instrument id=\"P2-I1\"><midi-program>29</midi-program></midi-instrument></score-part>
    <score-part id=\"P3\"><part-name>Electric Bass</part-name><midi-instrument id=\"P3-I1\"><midi-program>34</midi-program></midi-instrument></score-part>
  </part-list>
  <part id=\"P1\"><measure number=\"1\"><attributes><divisions>1</divisions></attributes><note><pitch><step>E</step><octave>4</octave></pitch><duration>1</duration></note></measure></part>
  <part id=\"P2\"><measure number=\"1\"><attributes><divisions>1</divisions></attributes><note><pitch><step>B</step><octave>3</octave></pitch><duration>1</duration></note></measure></part>
  <part id=\"P3\"><measure number=\"1\"><attributes><divisions>1</divisions></attributes><note><pitch><step>E</step><octave>2</octave></pitch><duration>1</duration></note></measure></part>
</score-partwise>
"""


def _score(tmp_path: Path) -> Path:
    path = tmp_path / "song.musicxml"
    path.write_text(MUSICXML, encoding="utf-8")
    return path


def test_imports_explicit_lead_rhythm_and_bass_parts(tmp_path: Path) -> None:
    project = tmp_path / "project"
    score = _score(tmp_path)

    result = import_project_musicxml_arrangements(
        project,
        score,
        selections=[
            MusicXMLArrangementSelection(instrument="lead", part_index=0),
            MusicXMLArrangementSelection(instrument="rhythm", part_index=1),
            MusicXMLArrangementSelection(instrument="bass", part_index=2),
        ],
    )

    assert set(result.outputs) == {"lead", "rhythm", "bass"}
    assert all(Path(path).is_file() for path in result.outputs.values())
    assert len(set(result.outputs.values())) == 3

    manifest_path = Path(result.manifest_path)
    assert manifest_path.is_file()
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["source_filename"] == "song.musicxml"
    assert payload["source_sha256"] == result.source_sha256
    assert [(item["instrument"], item["part_index"], item["part_name"]) for item in payload["arrangements"]] == [
        ("lead", 0, "Lead Guitar"),
        ("rhythm", 1, "Rhythm Guitar"),
        ("bass", 2, "Electric Bass"),
    ]
    assert all(not Path(item["output_json"]).is_absolute() for item in payload["arrangements"])
    assert all((project / item["output_json"]).is_file() for item in payload["arrangements"])


def test_manifest_is_deterministic_for_same_source_and_selection(tmp_path: Path) -> None:
    project = tmp_path / "project"
    score = _score(tmp_path)
    selections = [MusicXMLArrangementSelection(instrument="bass", part_index=2)]

    first = import_project_musicxml_arrangements(project, score, selections=selections)
    first_text = Path(first.manifest_path).read_text(encoding="utf-8")
    second = import_project_musicxml_arrangements(project, score, selections=selections)

    assert first.manifest_path == second.manifest_path
    assert Path(second.manifest_path).read_text(encoding="utf-8") == first_text


def test_rejects_duplicate_part_assignment(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="same MusicXML part"):
        import_project_musicxml_arrangements(
            tmp_path / "project",
            _score(tmp_path),
            selections=[
                MusicXMLArrangementSelection(instrument="lead", part_index=0),
                MusicXMLArrangementSelection(instrument="rhythm", part_index=0),
            ],
        )


def test_rejects_duplicate_role(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="role may be selected at most once"):
        import_project_musicxml_arrangements(
            tmp_path / "project",
            _score(tmp_path),
            selections=[
                MusicXMLArrangementSelection(instrument="lead", part_index=0),
                MusicXMLArrangementSelection(instrument="lead", part_index=1),
            ],
        )


def test_rejects_unknown_part_before_writing(tmp_path: Path) -> None:
    project = tmp_path / "project"
    with pytest.raises(ValueError, match="out of range"):
        import_project_musicxml_arrangements(
            project,
            _score(tmp_path),
            selections=[MusicXMLArrangementSelection(instrument="bass", part_index=9)],
        )

    assert not (project / "sources").exists()


def test_requires_at_least_one_selection(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="At least one"):
        import_project_musicxml_arrangements(
            tmp_path / "project",
            _score(tmp_path),
            selections=[],
        )
