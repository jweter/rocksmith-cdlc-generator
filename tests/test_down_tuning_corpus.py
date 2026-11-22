"""Synthetic independent tuning corpus for canonical #796 slice 37.

MIDI indices below are manually enumerated at the declared string pitches;
the corpus never reads commercial audio, infers tuning, or promotes notes.
"""
from __future__ import annotations

import pytest

from rocksmith_cdlc_generator.fretboard import (
    BassTuning, candidate_positions as bass_positions,
)
from rocksmith_cdlc_generator.fretboard_candidate_inventory import (
    build_fretboard_candidate_inventory,
)
from rocksmith_cdlc_generator.guitar_authoring import GuitarAuthoringChart
from rocksmith_cdlc_generator.instrument_audio_focus import (
    candidate_positions, focus_profile,
)
from rocksmith_cdlc_generator.rocksmith_xml import rocksmith_guitar_tuning_offsets
from rocksmith_cdlc_generator.song_preview_fretboard import note_matches_explicit_tuning
from rocksmith_cdlc_generator.source_import import (
    ImportedSource, SourceNoteEvent, SourceProvenance, SourceTrack,
)

# Physical string order: lowest-index string is the lowest-pitched string.
# Each offset is relative to 6-string E-A-D-G-B-E (40,45,50,55,59,64).
GUITAR_CASES = [
    ("E standard", (40, 45, 50, 55, 59, 64), (0, 0, 0, 0, 0, 0),
     ((0, 24), (1, 19), (2, 14), (3, 9), (4, 5), (5, 0))),
    ("Drop D", (38, 45, 50, 55, 59, 64), (-2, 0, 0, 0, 0, 0),
     ((1, 19), (2, 14), (3, 9), (4, 5), (5, 0))),
    ("Eb standard", (39, 44, 49, 54, 58, 63), (-1, -1, -1, -1, -1, -1),
     ((1, 20), (2, 15), (3, 10), (4, 6), (5, 1))),
    ("D standard", (38, 43, 48, 53, 57, 62), (-2, -2, -2, -2, -2, -2),
     ((1, 21), (2, 16), (3, 11), (4, 7), (5, 2))),
    ("DADGAD", (38, 45, 50, 55, 57, 62), (-2, 0, 0, 0, -2, -2),
     ((1, 19), (2, 14), (3, 9), (4, 7), (5, 2))),
    ("Drop C", (36, 43, 48, 53, 57, 62), (-4, -2, -2, -2, -2, -2),
     ((1, 21), (2, 16), (3, 11), (4, 7), (5, 2))),
]

BASS_CASES = [
    ("E standard", (28, 33, 38, 43)),
    ("Drop D", (26, 33, 38, 43)),
    ("Eb standard", (27, 32, 37, 42)),
    ("D standard", (26, 31, 36, 41)),
    ("Five-string BEADG", (23, 28, 33, 38, 43)),
]


def _source(role: str, tuning: tuple[int, ...], note_midi: int, fret: int) -> ImportedSource:
    return ImportedSource(
        provenance=SourceProvenance(
            source_type="synthetic", source_filename="synthetic",
            source_sha256="c" * 64, importer="test", importer_version="1",
        ),
        tracks=[SourceTrack(
            source_track_index=2, instrument=role, tuning_midi=list(tuning),
            notes=[SourceNoteEvent(
                start_seconds=0.5, duration_seconds=0.5, midi=note_midi,
                string_index=len(tuning) - 1, fret=fret, import_confidence=0.7,
            )],
        )],
    )


@pytest.mark.parametrize(("name", "tuning", "offsets", "expected"), GUITAR_CASES)
@pytest.mark.parametrize("role", ["lead", "rhythm"])
def test_guitar_down_tuning_midi64_consistent_across_real_candidate_export_paths(
    name: str, tuning: tuple[int, ...], offsets: tuple[int, ...],
    expected: tuple[tuple[int, int], ...], role: str,
) -> None:
    """Independent exact-fret oracle matches both listening and inventory paths."""
    assert candidate_positions(64, tuning) == expected, name
    assert candidate_positions(tuning[0], tuning) == ((0, 0),), name
    assert focus_profile(role, tuning).tuning_midi == tuning
    assert focus_profile(role, tuning).low_hz == pytest.approx(
        max(10.0, 440.0 * 2 ** ((tuning[0] - 69) / 12) / 2), abs=0.001
    )
    fret = 64 - tuning[-1]
    source = _source(role, tuning, 64, fret)
    inventory = build_fretboard_candidate_inventory(source, source_track_index=2)
    event = inventory.events[0]
    assert tuple((item.string_index, item.fret) for item in event.candidates) == expected
    assert event.source_position_status == "candidate"
    assert note_matches_explicit_tuning(
        source.tracks[0].notes[0], instrument=role, tuning_midi=list(tuning),
    )
    chart = GuitarAuthoringChart(
        arrangement=role, source_sha256="c" * 64,
        alignment_confidence=1.0, tuning_midi=tuning,
    )
    assert rocksmith_guitar_tuning_offsets(chart) == offsets
    assert source.tracks[0].tuning_midi == list(tuning)
    assert source.tracks[0].notes[0].fret == fret


@pytest.mark.parametrize(("name", "tuning"), BASS_CASES)
def test_bass_down_tuning_does_not_infer_e_standard(name: str, tuning: tuple[int, ...]) -> None:
    assert candidate_positions(tuning[0], tuning) == ((0, 0),), name
    assert focus_profile("bass", tuning).tuning_midi == tuning
    if len(tuning) == 4:
        mapped = bass_positions(tuning[0], BassTuning(name=name, open_midi=tuning))
        assert [(pos.string, pos.fret) for pos in mapped] == [(0, 0)]
    source = _source("bass", tuning, tuning[-1], 0)
    inventory = build_fretboard_candidate_inventory(source, source_track_index=2)
    assert inventory.events[0].source_position_status == "candidate"
    assert (len(tuning) - 1, 0) in [
        (p.string_index, p.fret) for p in inventory.events[0].candidates
    ]


def test_drop_d_open_low_note_is_unplayable_as_standard_guitar() -> None:
    standard = GUITAR_CASES[0][1]
    drop_d = GUITAR_CASES[1][1]
    assert candidate_positions(38, drop_d) == ((0, 0),)
    assert candidate_positions(38, standard) == ()
    assert candidate_positions(43, drop_d) == ((0, 5),)
    assert candidate_positions(43, standard) == ((0, 3),)
    # Bad source coordinate must remain inconsistent, not be silently snapped.
    source = _source("rhythm", standard, 43, 0)
    source.tracks[0].notes[0].string_index = 0
    source.tracks[0].notes[0].fret = 5
    event = build_fretboard_candidate_inventory(source, source_track_index=2).events[0]
    assert event.source_position_status == "inconsistent"
    assert [(p.string_index, p.fret) for p in event.candidates] == [(0, 3)]


@pytest.mark.parametrize("tuning", [
    None, [], [True, 45, 50, 55, 59, 64],
    [40.0, 45, 50, 55, 59, 64], [-1, 45, 50, 55, 59, 64],
    [128, 45, 50, 55, 59, 64],
])
def test_raw_candidate_position_rejects_untrusted_fake_open_string_pitches(tuning) -> None:
    with pytest.raises(ValueError):
        candidate_positions(64, tuning)


@pytest.mark.parametrize("bad_fret", [-1, True, 31, 3.5])
def test_down_tuned_candidate_fret_bound_is_exact_integer(bad_fret) -> None:
    with pytest.raises(ValueError, match="highest_fret"):
        candidate_positions(64, GUITAR_CASES[1][1], highest_fret=bad_fret)


@pytest.mark.parametrize("role,tuning", [
    ("lead", [38, 45, 50, 55, 59]), ("rhythm", [38, 45, 50]),
    ("bass", [26, 33, 38]), ("drums", [38, 45, 50, 55, 59, 64]),
])
def test_inventory_refuses_bad_role_or_string_count(role: str, tuning: list[int]) -> None:
    source = _source("lead", GUITAR_CASES[1][1], 64, 0)
    source.tracks[0].instrument = role
    source.tracks[0].tuning_midi = tuning
    with pytest.raises(ValueError, match="valid role-specific source tuning"):
        build_fretboard_candidate_inventory(source, source_track_index=2)


@pytest.mark.parametrize("bad_fret", [True, 31, -1, 3.5])
def test_inventory_fret_bound_rejects_phantom_playability(bad_fret) -> None:
    source = _source("lead", GUITAR_CASES[1][1], 64, 0)
    with pytest.raises(ValueError, match="max_fret"):
        build_fretboard_candidate_inventory(source, source_track_index=2, max_fret=bad_fret)
