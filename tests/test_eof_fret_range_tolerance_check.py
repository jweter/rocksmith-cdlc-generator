from __future__ import annotations

from types import SimpleNamespace as NS

import pytest

from rocksmith_cdlc_generator.eof_fret_range_tolerance_check import (
    DEFAULT_FRET_RANGE_TOLERANCE,
    EOF_UPSTREAM_COMMIT,
    EOF_UPSTREAM_FUNCTION,
    EOF_UPSTREAM_REPOSITORY,
    EOFFretRangeToleranceCheckError,
    compute_eof_fret_range_tolerance_check,
)

# --- Synthetic PyGuitarPro-shaped fixture helpers ---------------------------------------
#
# Mirrors the SimpleNamespace-based fixture convention used by
# tests/test_eof_short_note_truncation_check.py and tests/test_eof_rest_boundary_check.py.

_QUARTER_TICKS = 960


def gp_note(string_no: int, fret: int):
    return NS(string=string_no, value=fret)


def gp_beat(start_tick: int, notes: list | None = None):
    return NS(start=start_tick, notes=notes or [])


def gp_measure(beats: list):
    return NS(voices=[NS(beats=beats)])


def gp_track(measures: list):
    return NS(measures=measures)


def gp_song(track, *, tempo: int = 120):
    return NS(tempo=tempo, tracks=[track])


def _tick(offset_from_zero: int) -> int:
    return _QUARTER_TICKS + offset_from_zero


def _make_song(chord_frets: list[list[int]]) -> object:
    """Build a synthetic one-measure track with one chord per beat, evenly spaced."""

    beats = [
        gp_beat(_tick(index * _QUARTER_TICKS), [gp_note(1, fret) for fret in frets])
        for index, frets in enumerate(chord_frets)
    ]
    return gp_song(gp_track([gp_measure(beats)]))


# --- Core tolerance rule -------------------------------------------------------------------


def test_single_chord_establishes_initial_position_without_a_second_one():
    song = _make_song([[5]])

    report = compute_eof_fret_range_tolerance_check(song, track_index=0, source_sha256="a" * 64)

    assert report.chord_count == 1
    assert len(report.required_positions) == 1
    assert report.required_positions[0].fret == 5
    assert report.matches_generator_output is False


def test_consecutive_chords_within_tolerance_share_one_position():
    # 5, 6, 7, 8 all fit within a 4-fret span (5..8).
    song = _make_song([[5], [6], [7], [8]])

    report = compute_eof_fret_range_tolerance_check(song, track_index=0, source_sha256="a" * 64)

    assert report.chord_count == 4
    assert len(report.required_positions) == 1
    assert report.required_positions[0].fret == 5


def test_a_far_chord_forces_a_new_position():
    song = _make_song([[5], [12]])

    report = compute_eof_fret_range_tolerance_check(song, track_index=0, source_sha256="a" * 64)

    assert len(report.required_positions) == 2
    assert [p.fret for p in report.required_positions] == [5, 12]
    second = report.required_positions[1].event
    assert second.lowest_fret == 12
    assert second.highest_fret == 12


def test_exactly_at_tolerance_boundary_does_not_force_a_change():
    # lowest=5, highest=8: span is 4 frets (8-5+1=4), exactly at the default tolerance.
    song = _make_song([[5], [5, 8]])

    report = compute_eof_fret_range_tolerance_check(song, track_index=0, source_sha256="a" * 64)

    assert len(report.required_positions) == 1


def test_one_fret_beyond_tolerance_boundary_forces_a_change():
    # lowest=5, highest=9: span is 5 frets, exceeding the default 4-fret tolerance.
    song = _make_song([[5], [5, 9]])

    report = compute_eof_fret_range_tolerance_check(song, track_index=0, source_sha256="a" * 64)

    assert len(report.required_positions) == 2


def test_window_widens_within_tolerance_as_lower_notes_arrive():
    # First chord at fret 8 alone; second chord at fret 5 alone. Merged span 5..8 (4 frets) is
    # still within tolerance, so no second position is required, and the window's lowest edge
    # updates to 5.
    song = _make_song([[8], [5]])

    report = compute_eof_fret_range_tolerance_check(song, track_index=0, source_sha256="a" * 64)

    assert len(report.required_positions) == 1
    assert report.required_positions[0].fret == 8


# --- Open strings ----------------------------------------------------------------------------


def test_open_only_chord_is_skipped_via_lookahead_to_next_fretted_chord():
    # An open-string chord between two chords at fret 5 must not force any position change,
    # and must not appear as its own position: EOF looks ahead to the next fretted chord.
    song = _make_song([[5], [0], [5]])

    report = compute_eof_fret_range_tolerance_check(song, track_index=0, source_sha256="a" * 64)

    assert report.chord_count == 3
    assert len(report.required_positions) == 1
    assert report.required_positions[0].event.measure_index == 0


def test_leading_open_only_chord_defers_to_the_first_fretted_chord():
    song = _make_song([[0], [12]])

    report = compute_eof_fret_range_tolerance_check(song, track_index=0, source_sha256="a" * 64)

    assert len(report.required_positions) == 1
    assert report.required_positions[0].fret == 12


def test_trailing_open_only_chord_never_forces_a_position_of_its_own():
    song = _make_song([[5], [0]])

    report = compute_eof_fret_range_tolerance_check(song, track_index=0, source_sha256="a" * 64)

    assert len(report.required_positions) == 1
    assert report.required_positions[0].fret == 5


# --- Custom tolerance ------------------------------------------------------------------------


def test_custom_wider_tolerance_accepts_a_span_the_default_would_reject():
    song = _make_song([[5], [9]])

    default_report = compute_eof_fret_range_tolerance_check(song, track_index=0, source_sha256="a" * 64)
    wide_report = compute_eof_fret_range_tolerance_check(
        song, track_index=0, source_sha256="a" * 64, fret_range_tolerance=5
    )

    assert len(default_report.required_positions) == 2
    assert len(wide_report.required_positions) == 1


def test_default_tolerance_constant_matches_eof_main_c_default():
    assert DEFAULT_FRET_RANGE_TOLERANCE == 4


# --- Reason / evidence text --------------------------------------------------------------------


def test_reason_names_the_empty_anchors_gap_when_positions_are_required():
    song = _make_song([[5], [12]])

    report = compute_eof_fret_range_tolerance_check(song, track_index=0, source_sha256="a" * 64)

    assert "anchors" in report.reason
    assert "unimplemented gap" in report.reason
    assert report.generator_anchor_count == 0


def test_report_records_upstream_provenance():
    song = _make_song([[5]])

    report = compute_eof_fret_range_tolerance_check(song, track_index=0, source_sha256="a" * 64)

    assert report.upstream_repository == EOF_UPSTREAM_REPOSITORY == "raynebc/editor-on-fire"
    assert report.upstream_commit == EOF_UPSTREAM_COMMIT == "c0d88eabf7b00b0bd2cac9414df9fa9c6b3e7100"
    assert report.upstream_function == EOF_UPSTREAM_FUNCTION == "eof_note_can_be_played_within_fret_tolerance"
    assert "barre" in report.navigation_note


# --- Error handling ----------------------------------------------------------------------------


def test_track_index_out_of_range_raises():
    song = _make_song([[5]])

    with pytest.raises(EOFFretRangeToleranceCheckError, match="track index"):
        compute_eof_fret_range_tolerance_check(song, track_index=5, source_sha256="a" * 64)


def test_no_measures_raises():
    song = gp_song(gp_track([]))

    with pytest.raises(EOFFretRangeToleranceCheckError, match="no measures"):
        compute_eof_fret_range_tolerance_check(song, track_index=0, source_sha256="a" * 64)


def test_non_positive_tolerance_raises():
    song = _make_song([[5]])

    with pytest.raises(EOFFretRangeToleranceCheckError, match="positive"):
        compute_eof_fret_range_tolerance_check(
            song, track_index=0, source_sha256="a" * 64, fret_range_tolerance=0
        )


def test_beats_with_no_notes_are_skipped():
    song = gp_song(gp_track([gp_measure([gp_beat(_tick(0), notes=[])])]))

    report = compute_eof_fret_range_tolerance_check(song, track_index=0, source_sha256="a" * 64)

    assert report.chord_count == 0
    assert report.required_positions == []
    assert "nothing to check" in report.reason


def test_track_with_only_open_strings_never_establishes_a_position():
    # No fretted content ever appears, so the position stays uninitialized throughout --
    # matching EOF's own final flush condition (current_low == last_anchor == 0 writes nothing).
    song = _make_song([[0], [0]])

    report = compute_eof_fret_range_tolerance_check(song, track_index=0, source_sha256="a" * 64)

    assert report.chord_count == 2
    assert report.required_positions == []
    assert report.matches_generator_output is True
