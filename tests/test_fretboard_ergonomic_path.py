from __future__ import annotations

from rocksmith_cdlc_generator.fretboard_candidate_inventory import (
    build_fretboard_candidate_inventory,
)
from rocksmith_cdlc_generator.fretboard_ergonomic_path import (
    ErgonomicFingeringPath,
    build_ergonomic_fingering_path,
)
from rocksmith_cdlc_generator.source_import import (
    ImportedSource,
    SourceNoteEvent,
    SourceProvenance,
    SourceTrack,
)

_TUNING = [40, 45, 50, 55, 59, 64]  # standard six-string guitar, low to high


def _source(notes: list[SourceNoteEvent], *, tuning: list[int] | None = None) -> ImportedSource:
    return ImportedSource(
        provenance=SourceProvenance(
            source_type="gp5",
            source_filename="synthetic.gp5",
            source_sha256="b" * 64,
            importer="test",
            importer_version="1",
        ),
        tracks=[
            SourceTrack(
                source_track_index=2,
                name="Phrase",
                instrument="lead",
                tuning_midi=tuning if tuning is not None else list(_TUNING),
                notes=notes,
            )
        ],
    )


def _note(midi: int, *, string_index: int | None = None, fret: int | None = None) -> SourceNoteEvent:
    return SourceNoteEvent(
        start_seconds=0.0,
        duration_seconds=0.5,
        midi=midi,
        string_index=string_index,
        fret=fret,
        import_confidence=1.0,
    )


def _path(notes: list[SourceNoteEvent]) -> ErgonomicFingeringPath:
    source = _source(notes)
    inventory = build_fretboard_candidate_inventory(source, source_track_index=2)
    return build_ergonomic_fingering_path(inventory)


def test_pins_explicit_valid_source_position_and_never_moves_it() -> None:
    # MIDI 67 is explicitly fretted at string 5 fret 3 and is pitch-correct there;
    # MIDI 67 is also reachable at string 4 fret 8, string 3 fret 12, etc. The
    # explicit position must be kept exactly, never reassigned to the ergonomic
    # alternative even though other candidates exist.
    notes = [_note(67, string_index=5, fret=3)]

    path = _path(notes)

    assert len(path.choices) == 1
    assert (path.choices[0].string_index, path.choices[0].fret) == (5, 3)
    assert path.choices[0].fingering_source == "explicit_score"
    assert path.ergonomic_suggestion_count == 0


def test_ambiguous_event_is_pulled_toward_explicit_anchor_neighbors() -> None:
    # Event 0 is explicitly anchored at (5, 3). Event 1 (MIDI 69) has no declared
    # position and is reachable at (3, 14), (4, 10), or (5, 5); the ergonomically
    # closest to the anchor is (5, 5) (fret distance 2, same string).
    notes = [
        _note(67, string_index=5, fret=3),
        _note(69),
    ]

    path = _path(notes)

    assert path.choices[0].fingering_source == "explicit_score"
    assert (path.choices[1].string_index, path.choices[1].fret) == (5, 5)
    assert path.choices[1].fingering_source == "ergonomic_suggestion"
    assert path.total_hand_travel == 2


def test_fully_ambiguous_phrase_minimizes_total_hand_travel_deterministically() -> None:
    # No explicit positions anywhere: every event must be resolved purely
    # ergonomically. Staying on one string (e.g. (5, 0) -> (5, 3)) always costs the
    # full 3-semitone fret interval (3), but this synthetic tuning's uniform
    # perfect-fourth (5-semitone) string spacing makes a one-string, one-fret
    # diagonal shift -- (3, 9) -> (4, 8) -- strictly cheaper, at a total cost of 2.
    notes = [_note(64), _note(67)]

    path = _path(notes)

    assert [choice.fingering_source for choice in path.choices] == [
        "ergonomic_suggestion",
        "ergonomic_suggestion",
    ]
    assert [(choice.string_index, choice.fret) for choice in path.choices] == [(3, 9), (4, 8)]
    assert path.total_hand_travel == 2


def test_pitch_inconsistent_explicit_position_is_not_treated_as_an_anchor() -> None:
    # The declared (0, 3) does not actually produce MIDI 67 under this tuning
    # (open string 0 is MIDI 40, so fret 3 there is MIDI 43) -- it is physically
    # wrong and must not be respected as an anchor; it is resolved like "missing".
    notes = [_note(67, string_index=0, fret=3)]
    source = _source(notes)
    inventory = build_fretboard_candidate_inventory(source, source_track_index=2)
    assert inventory.events[0].source_position_status == "inconsistent"

    path = build_ergonomic_fingering_path(inventory)

    assert path.choices[0].fingering_source == "ergonomic_suggestion"
    assert (path.choices[0].string_index, path.choices[0].fret) != (0, 3)
    # Source note itself is never mutated by this read-model computation.
    assert (source.tracks[0].notes[0].string_index, source.tracks[0].notes[0].fret) == (0, 3)


def test_tie_broken_by_lowest_string_then_lowest_fret_for_determinism() -> None:
    # A single fully ambiguous event with no neighbors: every pitch-correct
    # candidate has equal (zero) path cost, so the lowest string/fret candidate
    # (the lowest open-string reach) must always be chosen.
    notes = [_note(64)]

    path = _path(notes)

    assert (path.choices[0].string_index, path.choices[0].fret) == (0, 24)


def test_round_trips_through_json() -> None:
    notes = [_note(64), _note(67, string_index=5, fret=3), _note(69)]

    path = _path(notes)
    payload = path.model_dump()

    assert ErgonomicFingeringPath.model_validate_json(path.model_dump_json()).model_dump() == payload
    assert payload["ergonomic_suggestion_count"] == 2


def test_empty_inventory_produces_empty_path() -> None:
    from rocksmith_cdlc_generator.fretboard_candidate_inventory import FretboardCandidateInventory

    empty_inventory = FretboardCandidateInventory(
        source_sha256="c" * 64,
        source_track_index=0,
        tuning_midi=list(_TUNING),
        max_fret=24,
        events=[],
    )

    path = build_ergonomic_fingering_path(empty_inventory)

    assert path.choices == []
    assert path.total_hand_travel == 0
    assert path.ergonomic_suggestion_count == 0
