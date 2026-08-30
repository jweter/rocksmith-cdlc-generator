from __future__ import annotations

from types import SimpleNamespace as NS

import pytest

from rocksmith_cdlc_generator.eof_rest_boundary_check import (
    EOF_UPSTREAM_COMMIT,
    EOF_UPSTREAM_FUNCTION,
    EOF_UPSTREAM_PATH,
    EOF_UPSTREAM_REPOSITORY,
    EOFRestBoundaryCheckError,
    compute_eof_rest_boundary_check,
    extract_explicit_rest_intervals,
    extract_note_intervals,
)


# --- Synthetic PyGuitarPro-shaped fixture helpers ---------------------------------------
#
# These mirror the SimpleNamespace-based fixture convention used by
# tests/test_eof_repeat_unfolding.py and tests/test_guitarpro_import.py: hand-built objects
# that duck-type the subset of PyGuitarPro's parsed Song/Track/Beat/Note attributes this
# module reads. No real Guitar Pro file, PyGuitarPro dependency, or commercial content is
# involved. Ticks follow guitarpro_import._normalized_tick's convention of a one-quarter-note
# (960 tick) leading offset, and quarter-note duration objects report time=960 to match
# PyGuitarPro's Duration.time for a plain quarter note at 960 quarterTime.

_QUARTER_TICKS = 960


def gp_duration(ticks: int = _QUARTER_TICKS):
    return NS(time=ticks)


def gp_note(string_no: int, fret: int):
    return NS(string=string_no, value=fret)


def gp_beat(start_tick: int, status_name: str, notes: list | None = None, duration_ticks: int = _QUARTER_TICKS):
    return NS(start=start_tick, status=NS(name=status_name), duration=gp_duration(duration_ticks), notes=notes or [])


def gp_measure(beats: list):
    return NS(voices=[NS(beats=beats)])


def gp_track(measures: list):
    return NS(measures=measures)


def gp_song(track, *, tempo: int = 120):
    return NS(tempo=tempo, tracks=[track])


def _tick(offset_from_zero: int) -> int:
    """Convert a zero-based tick offset into guitarpro_import's one-quarter-note-leading form."""
    return _QUARTER_TICKS + offset_from_zero


# --- No explicit rests ---------------------------------------------------------------------


def test_no_explicit_rests_is_trivially_respected():
    beats = [
        gp_beat(_tick(0), "normal", [gp_note(1, 3)]),
        gp_beat(_tick(_QUARTER_TICKS), "normal", [gp_note(1, 5)]),
    ]
    song = gp_song(gp_track([gp_measure(beats)]))

    report = compute_eof_rest_boundary_check(song, track_index=0, source_sha256="a" * 64)

    assert report.explicit_rest_count == 0
    assert report.note_count == 2
    assert report.boundaries_respected is True
    assert report.violations == []
    assert "nothing to check" in report.reason


def test_empty_status_beat_is_not_treated_as_an_explicit_rest():
    # A beat with BeatStatus.empty (no rest symbol, no notes) must not be counted as an
    # explicit rest: EOF only distinguishes "empty" from "rest" when logging, and this check
    # only enforces boundaries around explicitly authored rests.
    beats = [
        gp_beat(_tick(0), "normal", [gp_note(1, 3)]),
        gp_beat(_tick(_QUARTER_TICKS), "empty"),
        gp_beat(_tick(2 * _QUARTER_TICKS), "normal", [gp_note(1, 5)]),
    ]
    song = gp_song(gp_track([gp_measure(beats)]))

    report = compute_eof_rest_boundary_check(song, track_index=0, source_sha256="a" * 64)

    assert report.explicit_rest_count == 0
    assert report.note_count == 2


# --- Explicit rest with no violation --------------------------------------------------------


def test_notes_that_do_not_overlap_explicit_rest_are_respected():
    beats = [
        gp_beat(_tick(0), "normal", [gp_note(1, 3)]),
        gp_beat(_tick(_QUARTER_TICKS), "rest"),
        gp_beat(_tick(2 * _QUARTER_TICKS), "normal", [gp_note(1, 5)]),
    ]
    song = gp_song(gp_track([gp_measure(beats)]))

    report = compute_eof_rest_boundary_check(song, track_index=0, source_sha256="a" * 64)

    assert report.explicit_rest_count == 1
    assert report.note_count == 2
    assert report.boundaries_respected is True
    assert report.violations == []
    assert "no note sustain overlaps" in report.reason


# --- Explicit rest with a bleeding sustain ---------------------------------------------------


def test_note_sustain_overlapping_explicit_rest_is_reported():
    # The first note's authored duration (2 quarter notes, ending at t=1.0s) sustains through
    # the second half of a rest beat occupying [0.5s, 1.0s) -- exactly the "sustain bleeds
    # across a rest" defect shape the roadmap's item B names.
    beats = [
        gp_beat(_tick(0), "normal", [gp_note(1, 3)], duration_ticks=2 * _QUARTER_TICKS),
        gp_beat(_tick(_QUARTER_TICKS), "rest"),
    ]
    song = gp_song(gp_track([gp_measure(beats)]))

    report = compute_eof_rest_boundary_check(song, track_index=0, source_sha256="a" * 64)

    assert report.boundaries_respected is False
    assert len(report.violations) == 1
    violation = report.violations[0]
    assert violation.note.string_number == 1
    assert violation.note.fret == 3
    assert violation.overlap_seconds == pytest.approx(0.5, abs=1e-6)
    assert "overlap(s) found" in report.reason


def test_touching_endpoints_are_not_a_violation():
    # A note ending exactly where a rest begins (no overlap, only a shared boundary) must not
    # be flagged; only a strictly positive overlap beyond the tolerance is a violation.
    beats = [
        gp_beat(_tick(0), "normal", [gp_note(1, 3)]),
        gp_beat(_tick(_QUARTER_TICKS), "rest"),
    ]
    song = gp_song(gp_track([gp_measure(beats)]))

    report = compute_eof_rest_boundary_check(song, track_index=0, source_sha256="a" * 64)

    assert report.boundaries_respected is True
    assert report.violations == []


def test_multiple_notes_can_each_violate_the_same_rest():
    beats = [
        gp_beat(_tick(0), "normal", [gp_note(1, 3), gp_note(2, 5)], duration_ticks=2 * _QUARTER_TICKS),
        gp_beat(_tick(_QUARTER_TICKS), "rest"),
    ]
    song = gp_song(gp_track([gp_measure(beats)]))

    report = compute_eof_rest_boundary_check(song, track_index=0, source_sha256="a" * 64)

    assert report.boundaries_respected is False
    assert len(report.violations) == 2
    assert {violation.note.string_number for violation in report.violations} == {1, 2}


# --- Provenance -------------------------------------------------------------------------


def test_report_records_upstream_provenance():
    beats = [gp_beat(_tick(0), "rest")]
    song = gp_song(gp_track([gp_measure(beats)]))

    report = compute_eof_rest_boundary_check(song, track_index=0, source_sha256="a" * 64)

    assert report.upstream_repository == EOF_UPSTREAM_REPOSITORY == "raynebc/editor-on-fire"
    assert report.upstream_commit == EOF_UPSTREAM_COMMIT == "c0d88eabf7b00b0bd2cac9414df9fa9c6b3e7100"
    assert report.upstream_path == EOF_UPSTREAM_PATH == "src/gp_import.c"
    assert report.upstream_function == EOF_UPSTREAM_FUNCTION == "eof_load_gp"
    assert "truncation" in report.navigation_note


# --- Error handling / helper functions ---------------------------------------------------


def test_track_index_out_of_range_raises():
    song = gp_song(gp_track([gp_measure([gp_beat(_tick(0), "normal", [gp_note(1, 0)])])]))

    with pytest.raises(EOFRestBoundaryCheckError, match="track index"):
        compute_eof_rest_boundary_check(song, track_index=5, source_sha256="a" * 64)


def test_no_measures_raises():
    song = gp_song(gp_track([]))

    with pytest.raises(EOFRestBoundaryCheckError, match="no measures"):
        compute_eof_rest_boundary_check(song, track_index=0, source_sha256="a" * 64)


def test_negative_overlap_tolerance_raises():
    song = gp_song(gp_track([gp_measure([gp_beat(_tick(0), "normal", [gp_note(1, 0)])])]))

    with pytest.raises(EOFRestBoundaryCheckError, match="tolerance"):
        compute_eof_rest_boundary_check(
            song, track_index=0, source_sha256="a" * 64, overlap_tolerance_seconds=-1.0
        )


def test_extract_explicit_rest_intervals_ignores_zero_duration_rests():
    beats = [gp_beat(_tick(0), "rest", duration_ticks=0)]
    track = gp_track([gp_measure(beats)])
    tempo_points = [(0, 120.0)]

    intervals = extract_explicit_rest_intervals(track, tempo_points)

    assert intervals == []


def test_extract_note_intervals_ignores_zero_duration_beats():
    beats = [gp_beat(_tick(0), "normal", [gp_note(1, 0)], duration_ticks=0)]
    track = gp_track([gp_measure(beats)])
    tempo_points = [(0, 120.0)]

    intervals = extract_note_intervals(track, tempo_points)

    assert intervals == []
