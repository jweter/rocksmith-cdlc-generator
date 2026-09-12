from __future__ import annotations

from types import SimpleNamespace as NS

import pytest

from rocksmith_cdlc_generator.eof_repeat_unfolding import (
    EOF_UPSTREAM_COMMIT,
    EOF_UPSTREAM_PATH,
    EOF_UPSTREAM_REPOSITORY,
    EOFRepeatUnfoldingError,
    compute_eof_repeat_unfolding,
    extract_navigation_symbols,
    extract_repeat_markers,
    has_navigation_symbols,
    unfold_measure_sequence,
)


# --- Synthetic PyGuitarPro-shaped fixture helpers ---------------------------------------
#
# These mirror the SimpleNamespace-based fixture convention used by
# tests/test_guitarpro_import.py: hand-built objects that duck-type the subset of
# PyGuitarPro's parsed Song/Track/MeasureHeader/Beat/Note attributes this module reads.
# No real Guitar Pro file, PyGuitarPro dependency, or commercial content is involved.


def repeat_header(
    *,
    is_repeat_open: bool = False,
    repeat_close: int = -1,
    repeat_alternative: int = 0,
    direction: str | None = None,
    from_direction: str | None = None,
):
    return NS(
        isRepeatOpen=is_repeat_open,
        repeatClose=repeat_close,
        repeatAlternative=repeat_alternative,
        direction=NS(name=direction) if direction is not None else None,
        fromDirection=NS(name=from_direction) if from_direction is not None else None,
    )


def gp3_style_header(*, is_repeat_open: bool = False, repeat_close: int = -1, repeat_alternative: int = 0):
    """A GP3/GP4-style measure header: no ``direction``/``fromDirection`` attributes at all.

    PyGuitarPro's base ``MeasureHeader`` model does define both fields (defaulting to
    ``None``), but this fixture mirrors a stricter duck-typed object lacking them entirely,
    to prove ``extract_navigation_symbols`` degrades safely via ``getattr(..., None)`` rather
    than assuming the attributes exist.
    """

    return NS(isRepeatOpen=is_repeat_open, repeatClose=repeat_close, repeatAlternative=repeat_alternative)


def gp_note(string_no: int, fret: int):
    return NS(string=string_no, value=fret)


def gp_beat(start: int, notes: list):
    return NS(start=start, notes=notes)


def gp_measure(beats: list):
    return NS(voices=[NS(beats=beats)])


def gp_track(measures: list):
    return NS(measures=measures)


def gp_song(headers: list, track):
    return NS(measureHeaders=headers, tracks=[track])


def _single_note_measure(measure_index: int, string_no: int, fret: int):
    """A measure containing exactly one beat with one note, at a distinct tick per measure."""
    tick = measure_index * 3840
    return gp_measure([gp_beat(tick, [gp_note(string_no, fret)])])


# --- No repeats: identity passthrough ----------------------------------------------------


def test_no_repeat_markers_is_identity_passthrough():
    headers = [repeat_header(), repeat_header(), repeat_header()]
    track = gp_track([_single_note_measure(i, 1, i) for i in range(3)])
    song = gp_song(headers, track)

    report = compute_eof_repeat_unfolding(song, track_index=0, source_sha256="a" * 64)

    assert report.has_repeat_or_alt_ending_markers is False
    assert report.generator_measure_sequence == [0, 1, 2]
    assert report.eof_measure_sequence == [0, 1, 2]
    assert report.sequence_matches is True
    assert report.first_divergence_position is None
    assert report.missing_measure_indices == []
    assert report.duplicated_measure_indices == []

    # First/last source-event identity matches for every realized measure.
    for generator_event, realized_event in zip(report.generator_events, report.realized_events):
        assert generator_event.written_measure_index == realized_event.written_measure_index
        assert generator_event.first_event == realized_event.first_event
        assert generator_event.last_event == realized_event.last_event


def test_no_song_level_measure_headers_fails_closed_to_passthrough():
    track = gp_track([_single_note_measure(i, 1, i) for i in range(2)])
    song = gp_song([], track)

    report = compute_eof_repeat_unfolding(song, track_index=0, source_sha256="b" * 64)

    assert report.has_repeat_or_alt_ending_markers is False
    assert report.eof_measure_sequence == [0, 1]
    assert report.sequence_matches is True


# --- Simple repeat start/end --------------------------------------------------------------


def test_simple_repeat_start_and_end_duplicates_the_repeated_block():
    # Measures: 0 (start of repeat), 1 (loop content), 2 (end of repeat, 1 extra pass).
    headers = [
        repeat_header(is_repeat_open=True),
        repeat_header(),
        repeat_header(repeat_close=1),
    ]
    track = gp_track([_single_note_measure(i, 1, i) for i in range(3)])
    song = gp_song(headers, track)

    report = compute_eof_repeat_unfolding(song, track_index=0, source_sha256="c" * 64)

    assert report.has_repeat_or_alt_ending_markers is True
    assert report.generator_measure_sequence == [0, 1, 2]
    assert report.eof_measure_sequence == [0, 1, 2, 0, 1, 2]
    assert report.sequence_matches is False
    assert report.first_divergence_position == 3
    assert report.duplicated_measure_indices == [0, 1, 2]
    assert report.missing_measure_indices == []
    assert "disagrees" in report.reason

    # The repeated occurrence of written measure 0 carries the same source-event identity as
    # its first occurrence: unfolding duplicates playback position, not authored identity.
    first_occurrence = report.realized_events[0]
    second_occurrence = report.realized_events[3]
    assert first_occurrence.written_measure_index == second_occurrence.written_measure_index == 0
    assert first_occurrence.first_event == second_occurrence.first_event
    assert first_occurrence.last_event == second_occurrence.last_event


# --- Repeat with 1st/2nd alternate endings -------------------------------------------------


def test_repeat_with_first_and_second_alternate_endings():
    # Measures: 0 (start of repeat), 1 (loop content),
    # 2 (1st ending: bit0, also the end of repeat), 3 (2nd ending: bit1, plain).
    headers = [
        repeat_header(is_repeat_open=True),
        repeat_header(),
        repeat_header(repeat_close=1, repeat_alternative=0b01),
        repeat_header(repeat_alternative=0b10),
    ]
    track = gp_track([_single_note_measure(i, 1, i) for i in range(4)])
    song = gp_song(headers, track)

    report = compute_eof_repeat_unfolding(song, track_index=0, source_sha256="d" * 64)

    assert report.has_repeat_or_alt_ending_markers is True
    assert report.generator_measure_sequence == [0, 1, 2, 3]
    # Pass 1 plays the 1st ending (measure 2) and repeats; pass 2 skips measure 2 (not its
    # pass) and plays the 2nd ending (measure 3) instead.
    assert report.eof_measure_sequence == [0, 1, 2, 0, 1, 3]
    assert report.sequence_matches is False
    assert report.first_divergence_position == 3
    assert report.duplicated_measure_indices == [0, 1]
    assert report.missing_measure_indices == []

    realized_written_indices = [event.written_measure_index for event in report.realized_events]
    assert realized_written_indices == [0, 1, 2, 0, 1, 3]

    # Measure 2 (1st ending) and measure 3 (2nd ending) are distinct authored measures with
    # distinct source-event identity, even though both close out a loop pass.
    first_ending_event = report.realized_events[2]
    second_ending_event = report.realized_events[5]
    assert first_ending_event.written_measure_index == 2
    assert second_ending_event.written_measure_index == 3
    assert first_ending_event.first_event != second_ending_event.first_event


def test_alternate_ending_never_reached_is_reported_as_missing():
    # A 2nd-ending measure whose bit can never be reached (repeat closes after only one pass)
    # is never realized: this should surface as a missing measure, not be silently dropped.
    headers = [
        repeat_header(is_repeat_open=True),
        repeat_header(repeat_close=0, repeat_alternative=0b01),  # 1st ending, no more passes
        repeat_header(repeat_alternative=0b10),  # 2nd ending: unreachable with 0 repeats
    ]
    track = gp_track([_single_note_measure(i, 1, i) for i in range(3)])
    song = gp_song(headers, track)

    report = compute_eof_repeat_unfolding(song, track_index=0, source_sha256="e" * 64)

    assert report.eof_measure_sequence == [0, 1]
    assert 2 in report.missing_measure_indices
    assert report.sequence_matches is False


# --- Navigation symbols (Da Capo/Da Segno/Coda/Fine) -----------------------------------


def test_da_capo_repeats_the_whole_piece_once_then_stops():
    headers = [
        repeat_header(),
        repeat_header(),
        repeat_header(from_direction="Da Capo"),
    ]
    track = gp_track([_single_note_measure(i, 1, i) for i in range(3)])
    song = gp_song(headers, track)

    report = compute_eof_repeat_unfolding(song, track_index=0, source_sha256="1" * 64)

    assert report.has_navigation_symbols is True
    assert report.eof_measure_sequence == [0, 1, 2, 0, 1, 2]
    assert report.sequence_matches is False


def test_da_segno_jumps_back_to_segno_measure_not_the_start():
    headers = [
        repeat_header(),
        repeat_header(direction="Segno"),
        repeat_header(),
        repeat_header(from_direction="Da Segno"),
    ]
    track = gp_track([_single_note_measure(i, 1, i) for i in range(4)])
    song = gp_song(headers, track)

    report = compute_eof_repeat_unfolding(song, track_index=0, source_sha256="2" * 64)

    assert report.eof_measure_sequence == [0, 1, 2, 3, 1, 2, 3]


def test_da_capo_al_fine_stops_at_the_fine_measure_on_the_second_pass():
    headers = [
        repeat_header(),
        repeat_header(direction="Fine"),
        repeat_header(from_direction="Da Capo al Fine"),
    ]
    track = gp_track([_single_note_measure(i, 1, i) for i in range(3)])
    song = gp_song(headers, track)

    report = compute_eof_repeat_unfolding(song, track_index=0, source_sha256="3" * 64)

    # First pass plays all 3 measures; the "Da Capo al Fine" jump replays from measure 0 and
    # stops as soon as the "Fine" measure (1) is reached again, never re-realizing measure 2.
    assert report.eof_measure_sequence == [0, 1, 2, 0, 1]


def test_da_capo_al_coda_skips_ahead_to_coda_on_da_coda():
    # Measure 2 is written between the "Da Coda" jump-off point (1) and the "Coda" landing
    # point (3): it must be played on the first pass (nothing has jumped yet) but skipped on
    # the second pass once "Da Capo al Coda" (4) has activated "Da Coda".
    headers = [
        repeat_header(),
        repeat_header(from_direction="Da Coda"),
        repeat_header(),
        repeat_header(direction="Coda"),
        repeat_header(from_direction="Da Capo al Coda"),
    ]
    track = gp_track([_single_note_measure(i, 1, i) for i in range(5)])
    song = gp_song(headers, track)

    report = compute_eof_repeat_unfolding(song, track_index=0, source_sha256="4" * 64)

    # Pass 1 (0..4): "Da Coda" (1) is not yet activated, so measure 2 plays normally; measure
    # 4's "Da Capo al Coda" then seeks back to measure 0 and activates "Da Coda".
    # Pass 2: 0, 1 -- now "Da Coda" fires and jumps straight to the Coda (3), skipping the
    # written measure 2 this time; measure 4's symbol was destroyed on first use, so this pass
    # ends after measure 4 is reached once more via plain advancement.
    assert report.eof_measure_sequence == [0, 1, 2, 3, 4, 0, 1, 3, 4]
    assert report.missing_measure_indices == []
    assert report.duplicated_measure_indices == [0, 1, 3, 4]


def test_da_segno_with_no_matching_segno_is_invalidated_and_ignored():
    # A "Da Segno" placed with no corresponding "Segno" anywhere is not a valid jump (EOF's own
    # destination-invalidation guard); the generator's written order should pass through as-is.
    headers = [
        repeat_header(),
        repeat_header(),
        repeat_header(from_direction="Da Segno"),
    ]
    track = gp_track([_single_note_measure(i, 1, i) for i in range(3)])
    song = gp_song(headers, track)

    report = compute_eof_repeat_unfolding(song, track_index=0, source_sha256="5" * 64)

    assert report.has_navigation_symbols is False
    assert report.eof_measure_sequence == [0, 1, 2]
    assert report.sequence_matches is True


def test_gp3_style_headers_without_direction_attributes_are_identity_passthrough():
    headers = [gp3_style_header(), gp3_style_header(), gp3_style_header()]
    track = gp_track([_single_note_measure(i, 1, i) for i in range(3)])
    song = gp_song(headers, track)

    report = compute_eof_repeat_unfolding(song, track_index=0, source_sha256="6" * 64)

    assert report.has_navigation_symbols is False
    assert report.eof_measure_sequence == [0, 1, 2]


def test_extract_navigation_symbols_and_has_navigation_symbols_helpers():
    headers = [
        repeat_header(direction="Coda"),
        repeat_header(from_direction="Da Capo al Coda"),
    ]
    song = gp_song(headers, gp_track([_single_note_measure(i, 1, i) for i in range(2)]))

    symbols = extract_navigation_symbols(song)

    assert len(symbols) == 19
    assert symbols[0] == 0  # Coda placed at measure 0
    assert symbols[6] == 1  # Da Capo al Coda placed at measure 1
    assert has_navigation_symbols(symbols) is True
    assert has_navigation_symbols([None] * 19) is False


# --- Provenance ------------------------------------------------------------------------


def test_report_records_upstream_provenance():
    headers = [repeat_header()]
    track = gp_track([_single_note_measure(0, 1, 0)])
    song = gp_song(headers, track)

    report = compute_eof_repeat_unfolding(song, track_index=0, source_sha256="f" * 64)

    assert report.upstream_repository == EOF_UPSTREAM_REPOSITORY == "raynebc/editor-on-fire"
    assert report.upstream_commit == EOF_UPSTREAM_COMMIT == "c0d88eabf7b00b0bd2cac9414df9fa9c6b3e7100"
    assert report.upstream_path == EOF_UPSTREAM_PATH == "src/gp_import.c"
    assert report.navigation_symbols_supported is True
    assert "Da Capo" in report.navigation_symbols_note


# --- Error handling / helper functions ---------------------------------------------------


def test_track_index_out_of_range_raises():
    headers = [repeat_header()]
    track = gp_track([_single_note_measure(0, 1, 0)])
    song = gp_song(headers, track)

    with pytest.raises(EOFRepeatUnfoldingError, match="track index"):
        compute_eof_repeat_unfolding(song, track_index=5, source_sha256="a" * 64)


def test_mismatched_header_and_measure_counts_raises():
    headers = [repeat_header(), repeat_header()]
    track = gp_track([_single_note_measure(0, 1, 0)])
    song = gp_song(headers, track)

    with pytest.raises(EOFRepeatUnfoldingError, match="does not match"):
        compute_eof_repeat_unfolding(song, track_index=0, source_sha256="a" * 64)


def test_extract_repeat_markers_reads_isolated_fields():
    headers = [
        repeat_header(is_repeat_open=True, repeat_close=-1, repeat_alternative=0),
        repeat_header(repeat_close=2, repeat_alternative=0b11),
    ]
    song = NS(measureHeaders=headers)

    markers = extract_repeat_markers(song)

    assert markers[0].start_of_repeat is True
    assert markers[0].num_of_repeats == 0
    assert markers[1].start_of_repeat is False
    assert markers[1].num_of_repeats == 2
    assert markers[1].alt_ending_mask == 0b11


def test_unfold_measure_sequence_empty_input():
    assert unfold_measure_sequence([]) == []
