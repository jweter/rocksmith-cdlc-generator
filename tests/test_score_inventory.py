from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from rocksmith_cdlc_generator.score_inventory import (
    inventory_guitarpro_song,
    inventory_musicxml,
)
from rocksmith_cdlc_generator.score_source import ArrangementRole


def _gp_track(name: str, program: int, tuning: list[int], note_count: int) -> SimpleNamespace:
    strings = [
        SimpleNamespace(number=index + 1, value=midi)
        for index, midi in enumerate(reversed(tuning))
    ]
    beat = SimpleNamespace(notes=[SimpleNamespace() for _ in range(note_count)])
    voice = SimpleNamespace(beats=[beat])
    measure = SimpleNamespace(voices=[voice])
    return SimpleNamespace(
        name=name,
        channel=SimpleNamespace(instrument=program),
        strings=strings,
        measures=[measure],
    )


def test_guitarpro_inventory_keeps_all_tracks_and_proposes_three_roles(tmp_path: Path) -> None:
    source = tmp_path / "song.gp5"
    source.write_bytes(b"fixture")
    song = SimpleNamespace(
        tracks=[
            _gp_track("Lead Guitar", 29, [40, 45, 50, 55, 59, 64], 12),
            _gp_track("Rhythm Guitar", 30, [40, 45, 50, 55, 59, 64], 18),
            _gp_track("Bass", 33, [28, 33, 38, 43], 9),
            _gp_track("Drums", 0, [], 20),
        ]
    )

    score = inventory_guitarpro_song(
        song,
        source_path=source,
        source_sha256="a" * 64,
        imported_relative_path="sources/song.gp5",
    )

    assert [track.name for track in score.tracks] == [
        "Lead Guitar",
        "Rhythm Guitar",
        "Bass",
        "Drums",
    ]
    assert [track.note_count for track in score.tracks] == [12, 18, 9, 20]
    assert score.tracks[0].tuning_midi == [40, 45, 50, 55, 59, 64]
    assert score.mapping_for(ArrangementRole.lead).source_track_index == 0
    assert score.mapping_for(ArrangementRole.rhythm).source_track_index == 1
    assert score.mapping_for(ArrangementRole.bass).source_track_index == 2
    assert score.mapping_for(ArrangementRole.lead).confidence == 1.0
    assert score.mapping_for(ArrangementRole.rhythm).confidence == 1.0
    assert score.mapping_for(ArrangementRole.bass).confidence == 1.0
    assert all(mapping.human_confirmed is False for mapping in score.arrangement_mappings)


def test_guitarpro_inventory_preserves_tied_role_as_unmapped(tmp_path: Path) -> None:
    source = tmp_path / "ambiguous.gp5"
    source.write_bytes(b"fixture")
    song = SimpleNamespace(
        tracks=[
            _gp_track("Guitar A", 29, [40, 45, 50, 55, 59, 64], 10),
            _gp_track("Guitar B", 29, [40, 45, 50, 55, 59, 64], 10),
        ]
    )

    score = inventory_guitarpro_song(
        song,
        source_path=source,
        source_sha256="b" * 64,
    )

    assert len(score.tracks) == 2
    assert score.mapping_for(ArrangementRole.lead) is None
    assert score.mapping_for(ArrangementRole.rhythm) is None
    assert score.mapping_for(ArrangementRole.bass) is None


def test_musicxml_inventory_reads_entire_score_before_arrangement_extraction(tmp_path: Path) -> None:
    source = tmp_path / "song.musicxml"
    source.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="4.0">
  <part-list>
    <score-part id="P1"><part-name>Lead Guitar</part-name><midi-instrument id="P1-I1"><midi-program>30</midi-program></midi-instrument></score-part>
    <score-part id="P2"><part-name>Rhythm Guitar</part-name><midi-instrument id="P2-I1"><midi-program>29</midi-program></midi-instrument></score-part>
    <score-part id="P3"><part-name>Bass</part-name><midi-instrument id="P3-I1"><midi-program>34</midi-program></midi-instrument></score-part>
  </part-list>
  <part id="P1"><measure number="1"><attributes><divisions>1</divisions><staff-details><staff-lines>6</staff-lines><staff-tuning line="1"><tuning-step>E</tuning-step><tuning-octave>4</tuning-octave></staff-tuning><staff-tuning line="2"><tuning-step>B</tuning-step><tuning-octave>3</tuning-octave></staff-tuning><staff-tuning line="3"><tuning-step>G</tuning-step><tuning-octave>3</tuning-octave></staff-tuning><staff-tuning line="4"><tuning-step>D</tuning-step><tuning-octave>3</tuning-octave></staff-tuning><staff-tuning line="5"><tuning-step>A</tuning-step><tuning-octave>2</tuning-octave></staff-tuning><staff-tuning line="6"><tuning-step>E</tuning-step><tuning-octave>2</tuning-octave></staff-tuning></staff-details></attributes><note><pitch><step>E</step><octave>4</octave></pitch><duration>1</duration></note></measure></part>
  <part id="P2"><measure number="1"><note><pitch><step>E</step><octave>3</octave></pitch><duration>1</duration></note><note><pitch><step>G</step><octave>3</octave></pitch><duration>1</duration></note></measure></part>
  <part id="P3"><measure number="1"><attributes><staff-details><staff-lines>4</staff-lines><staff-tuning line="1"><tuning-step>G</tuning-step><tuning-octave>2</tuning-octave></staff-tuning><staff-tuning line="2"><tuning-step>D</tuning-step><tuning-octave>2</tuning-octave></staff-tuning><staff-tuning line="3"><tuning-step>A</tuning-step><tuning-octave>1</tuning-octave></staff-tuning><staff-tuning line="4"><tuning-step>E</tuning-step><tuning-octave>1</tuning-octave></staff-tuning></staff-details></attributes><note><pitch><step>E</step><octave>2</octave></pitch><duration>1</duration></note></measure></part>
</score-partwise>
""",
        encoding="utf-8",
    )

    score = inventory_musicxml(source, imported_relative_path="sources/song.musicxml")

    assert len(score.tracks) == 3
    assert [track.note_count for track in score.tracks] == [1, 2, 1]
    assert score.tracks[0].tuning_midi == [40, 45, 50, 55, 59, 64]
    assert score.tracks[2].tuning_midi == [28, 33, 38, 43]
    assert score.mapping_for(ArrangementRole.lead).source_track_index == 0
    assert score.mapping_for(ArrangementRole.rhythm).source_track_index == 1
    assert score.mapping_for(ArrangementRole.bass).source_track_index == 2
    assert score.imported_relative_path == "sources/song.musicxml"
