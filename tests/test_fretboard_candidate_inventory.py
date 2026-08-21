from __future__ import annotations

import pytest

from rocksmith_cdlc_generator.fretboard_candidate_inventory import (
    build_fretboard_candidate_inventory,
)
from rocksmith_cdlc_generator.source_import import (
    ImportedSource,
    SourceNoteEvent,
    SourceProvenance,
    SourceTrack,
)


def _source(*, tuning: list[int] | None = None) -> ImportedSource:
    return ImportedSource(
        provenance=SourceProvenance(
            source_type="gp5",
            source_filename="synthetic.gp5",
            source_sha256="a" * 64,
            importer="test",
            importer_version="1",
        ),
        tracks=[
            SourceTrack(
                source_track_index=3,
                name="Ambiguous Lead",
                instrument="lead",
                tuning_midi=tuning if tuning is not None else [40, 45, 50, 55, 59, 64],
                notes=[
                    SourceNoteEvent(
                        start_seconds=0.0,
                        duration_seconds=0.5,
                        midi=64,
                        string_index=5,
                        fret=0,
                        import_confidence=1.0,
                    ),
                    SourceNoteEvent(
                        start_seconds=0.5,
                        duration_seconds=0.5,
                        midi=67,
                        string_index=5,
                        fret=3,
                        import_confidence=1.0,
                    ),
                ],
            )
        ],
    )


def test_enumerates_multiple_pitch_correct_positions_without_rewriting_source() -> None:
    source = _source()

    inventory = build_fretboard_candidate_inventory(source, source_track_index=3)

    assert inventory.ambiguous_event_count == 2
    assert [(item.string_index, item.fret) for item in inventory.events[0].candidates] == [
        (0, 24),
        (1, 19),
        (2, 14),
        (3, 9),
        (4, 5),
        (5, 0),
    ]
    assert (inventory.events[0].source_string_index, inventory.events[0].source_fret) == (5, 0)
    assert inventory.events[0].source_position_status == "candidate"
    assert inventory.source_position_match_count == 2
    assert inventory.missing_source_position_count == 0
    assert inventory.inconsistent_source_position_count == 0
    assert (source.tracks[0].notes[0].string_index, source.tracks[0].notes[0].fret) == (5, 0)


def test_classifies_missing_and_pitch_inconsistent_source_positions_without_mutation() -> None:
    source = _source()
    source.tracks[0].notes[0].string_index = None
    source.tracks[0].notes[0].fret = None
    source.tracks[0].notes[1].string_index = 0
    source.tracks[0].notes[1].fret = 3

    inventory = build_fretboard_candidate_inventory(source, source_track_index=3)

    assert [event.source_position_status for event in inventory.events] == [
        "missing",
        "inconsistent",
    ]
    assert inventory.source_position_match_count == 0
    assert inventory.missing_source_position_count == 1
    assert inventory.inconsistent_source_position_count == 1
    assert source.tracks[0].notes[0].string_index is None
    assert source.tracks[0].notes[1].string_index == 0


def test_max_fret_bounds_candidate_search_space_and_can_expose_out_of_bound_source_position() -> None:
    inventory = build_fretboard_candidate_inventory(_source(), source_track_index=3, max_fret=12)

    assert [(item.string_index, item.fret) for item in inventory.events[0].candidates] == [
        (3, 9),
        (4, 5),
        (5, 0),
    ]
    assert inventory.events[0].source_position_status == "candidate"


def test_requires_explicit_tuning() -> None:
    source = _source()
    source.tracks[0].tuning_midi = None

    with pytest.raises(ValueError, match="requires explicit source tuning"):
        build_fretboard_candidate_inventory(source, source_track_index=3)


def test_rejects_event_with_no_playable_position_in_bound() -> None:
    source = _source(tuning=[40, 45, 50, 55, 59, 64])
    source.tracks[0].notes[0].midi = 20

    with pytest.raises(ValueError, match="has no playable position"):
        build_fretboard_candidate_inventory(source, source_track_index=3)


def test_rejects_unknown_track_and_negative_fret_bound() -> None:
    source = _source()

    with pytest.raises(ValueError, match="source track 9 is not present"):
        build_fretboard_candidate_inventory(source, source_track_index=9)
    with pytest.raises(ValueError, match="max_fret must be non-negative"):
        build_fretboard_candidate_inventory(source, source_track_index=3, max_fret=-1)
