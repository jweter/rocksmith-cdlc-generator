from __future__ import annotations

from types import SimpleNamespace as NS

import pytest

from rocksmith_cdlc_generator.eof_short_note_truncation_check import (
    EOF_UPSTREAM_COMMIT,
    EOF_UPSTREAM_FUNCTION,
    EOF_UPSTREAM_PATH,
    EOF_UPSTREAM_REPOSITORY,
    EOFShortNoteTruncationCheckError,
    compute_eof_short_note_truncation_check,
)

# --- Synthetic PyGuitarPro-shaped fixture helpers ---------------------------------------
#
# Mirrors the SimpleNamespace-based fixture convention used by
# tests/test_eof_rest_boundary_check.py: hand-built objects that duck-type the subset of
# PyGuitarPro's parsed Song/Track/Beat/Note/NoteEffect attributes this module reads. No real
# Guitar Pro file, PyGuitarPro dependency, or commercial content is involved. Ticks follow
# guitarpro_import._normalized_tick's convention of a one-quarter-note (960 tick) leading
# offset, and duration objects report time=960 for a plain quarter note, matching
# PyGuitarPro's Duration.time at 960 quarterTime.

_QUARTER_TICKS = 960


def gp_effect(
    *,
    staccato: bool = False,
    palmMute: bool = False,
    vibrato: bool = False,
    slides: list | None = None,
    bend: object | None = None,
    tremoloPicking: object | None = None,
):
    return NS(
        staccato=staccato,
        palmMute=palmMute,
        vibrato=vibrato,
        slides=slides or [],
        bend=bend,
        tremoloPicking=tremoloPicking,
    )


def gp_note(string_no: int, fret: int, *, note_type: str = "normal", effect=None):
    return NS(string=string_no, value=fret, type=NS(name=note_type), effect=effect or gp_effect())


def gp_beat(start_tick: int, notes: list | None = None, duration_ticks: int = _QUARTER_TICKS):
    return NS(start=start_tick, duration=NS(time=duration_ticks), notes=notes or [])


def gp_measure(beats: list):
    return NS(voices=[NS(beats=beats)])


def gp_track(measures: list):
    return NS(measures=measures)


def gp_song(track, *, tempo: int = 120):
    return NS(tempo=tempo, tracks=[track])


def _tick(offset_from_zero: int) -> int:
    """Convert a zero-based tick offset into guitarpro_import's one-quarter-note-leading form."""
    return _QUARTER_TICKS + offset_from_zero


# --- Duration-based short notes -----------------------------------------------------------


def test_short_single_note_is_truncated_by_default_preferences():
    # A sixteenth note (240 ticks, below the 960-tick quarter-note threshold) on a single string.
    beats = [gp_beat(_tick(0), [gp_note(1, 3)], duration_ticks=240)]
    song = gp_song(gp_track([gp_measure(beats)]))

    report = compute_eof_short_note_truncation_check(song, track_index=0, source_sha256="a" * 64)

    assert report.eof_truncated_count == 1
    event = report.mismatches[0].event
    assert event.is_short_duration is True
    assert event.eof_would_truncate is True
    assert event.eof_predicted_sustain_seconds == pytest.approx(0.001)
    assert report.truncation_matches_eof_preferences is False
    assert "unimplemented gap" in report.reason


def test_quarter_note_or_longer_is_not_short():
    beats = [gp_beat(_tick(0), [gp_note(1, 3)], duration_ticks=_QUARTER_TICKS)]
    song = gp_song(gp_track([gp_measure(beats)]))

    report = compute_eof_short_note_truncation_check(song, track_index=0, source_sha256="a" * 64)

    assert report.eof_truncated_count == 0
    assert report.mismatches == []
    assert report.truncation_matches_eof_preferences is True


def test_short_note_generator_sustain_already_truncated_is_not_a_mismatch():
    # 1 tick at the default 120bpm tempo is already shorter than EOF's ~1ms truncated result
    # (960 ticks = one quarter note = 0.5s at 120bpm, so 1 tick is ~0.52ms), so a generator that
    # (by construction, however implausible in practice) already produced a shorter-than-EOF
    # sustain must not be reported as a mismatch: the mismatch signal is specifically "generator
    # sustain exceeds EOF's truncated result," not "generator disagrees with EOF at all."
    beats = [gp_beat(_tick(0), [gp_note(1, 3)], duration_ticks=1)]
    song = gp_song(gp_track([gp_measure(beats)]))

    report = compute_eof_short_note_truncation_check(song, track_index=0, source_sha256="a" * 64)

    assert report.eof_truncated_count == 1
    assert report.mismatches == []
    assert report.truncation_matches_eof_preferences is True


# --- Staccato forces short regardless of duration -----------------------------------------


def test_staccato_quarter_note_is_truncated_despite_normal_duration():
    beats = [
        gp_beat(
            _tick(0),
            [gp_note(1, 3, effect=gp_effect(staccato=True))],
            duration_ticks=_QUARTER_TICKS,
        )
    ]
    song = gp_song(gp_track([gp_measure(beats)]))

    report = compute_eof_short_note_truncation_check(song, track_index=0, source_sha256="a" * 64)

    event = report.mismatches[0].event
    assert event.is_short_duration is False
    assert event.is_staccato is True
    assert event.eof_would_truncate is True


# --- Technique exemptions override truncation ----------------------------------------------


@pytest.mark.parametrize(
    "effect_kwargs",
    [
        {"vibrato": True},
        {"slides": ["legatoSlideTo"]},
        {"bend": NS(points=[NS(value=5)])},
    ],
)
def test_technique_exempt_short_note_is_not_truncated(effect_kwargs):
    beats = [
        gp_beat(
            _tick(0),
            [gp_note(1, 3, effect=gp_effect(**effect_kwargs))],
            duration_ticks=240,
        )
    ]
    song = gp_song(gp_track([gp_measure(beats)]))

    report = compute_eof_short_note_truncation_check(song, track_index=0, source_sha256="a" * 64)

    event_list = [e for m in report.mismatches for e in [m.event]]
    assert event_list == []
    assert report.eof_truncated_count == 0
    assert report.truncation_matches_eof_preferences is True


def test_zero_height_bend_does_not_exempt():
    beats = [
        gp_beat(
            _tick(0),
            [gp_note(1, 3, effect=gp_effect(bend=NS(points=[NS(value=0)])))],
            duration_ticks=240,
        )
    ]
    song = gp_song(gp_track([gp_measure(beats)]))

    report = compute_eof_short_note_truncation_check(song, track_index=0, source_sha256="a" * 64)

    assert report.eof_truncated_count == 1
    assert report.mismatches[0].event.is_technique_exempt is False


def test_tremolo_picking_exempts_short_duration_but_not_mute():
    beats = [
        gp_beat(
            _tick(0),
            [gp_note(1, 3, note_type="dead", effect=gp_effect(tremoloPicking=NS()))],
            duration_ticks=240,
        )
    ]
    song = gp_song(gp_track([gp_measure(beats)]))

    report = compute_eof_short_note_truncation_check(song, track_index=0, source_sha256="a" * 64)

    event = report.mismatches[0].event
    assert event.is_fully_muted_or_palm_muted is True
    assert event.eof_would_truncate is True


# --- Mute / palm-mute truncate unconditionally on single notes -----------------------------


def test_fully_muted_single_note_truncates_regardless_of_duration():
    beats = [gp_beat(_tick(0), [gp_note(1, 3, note_type="dead")], duration_ticks=2 * _QUARTER_TICKS)]
    song = gp_song(gp_track([gp_measure(beats)]))

    report = compute_eof_short_note_truncation_check(song, track_index=0, source_sha256="a" * 64)

    event = report.mismatches[0].event
    assert event.is_short_duration is False
    assert event.is_fully_muted_or_palm_muted is True
    assert event.eof_would_truncate is True


def test_palm_muted_single_note_truncates_regardless_of_duration():
    beats = [
        gp_beat(
            _tick(0),
            [gp_note(1, 3, effect=gp_effect(palmMute=True))],
            duration_ticks=2 * _QUARTER_TICKS,
        )
    ]
    song = gp_song(gp_track([gp_measure(beats)]))

    report = compute_eof_short_note_truncation_check(song, track_index=0, source_sha256="a" * 64)

    assert report.eof_truncated_count == 1
    assert report.mismatches[0].event.is_fully_muted_or_palm_muted is True


def test_muted_chord_is_not_truncated_because_it_is_not_a_single_note():
    beats = [
        gp_beat(
            _tick(0),
            [gp_note(1, 3, note_type="dead"), gp_note(2, 5, note_type="dead")],
            duration_ticks=2 * _QUARTER_TICKS,
        )
    ]
    song = gp_song(gp_track([gp_measure(beats)]))

    report = compute_eof_short_note_truncation_check(song, track_index=0, source_sha256="a" * 64)

    assert report.eof_truncated_count == 0
    assert report.truncation_matches_eof_preferences is True


# --- A neighboring note's slide never exempts a note from truncation -----------------------


def test_previous_note_legato_slide_does_not_exempt_a_following_short_note():
    # Verified against EOF_UPSTREAM_COMMIT: truncation eligibility is decided per note
    # (gp_import.c ~4191-4218) strictly before the only two passes that walk the cross-beat
    # note sequence ("Correct slide directions" ~4498, "Convert slide in from above/below" ~4595),
    # so a previous note's shift/legato slide-to status cannot exempt the following note. Only a
    # slide notated directly on a note's own effect exempts that note.
    beats = [
        gp_beat(_tick(0), [gp_note(1, 3, effect=gp_effect(slides=["legatoSlideTo"]))], duration_ticks=240),
        gp_beat(_tick(240), [gp_note(1, 5)], duration_ticks=240),
    ]
    song = gp_song(gp_track([gp_measure(beats)]))

    report = compute_eof_short_note_truncation_check(song, track_index=0, source_sha256="a" * 64)

    # The slide source note is exempt via its own slide effect and never appears as a mismatch;
    # the following note, despite being the target of that slide, gets no exemption of its own.
    assert report.note_count == 2
    assert report.eof_truncated_count == 1
    assert len(report.mismatches) == 1
    following = report.mismatches[0].event
    assert following.fret == 5
    assert following.is_technique_exempt is False
    assert following.eof_would_truncate is True


# --- Chords are never truncated under EOF's default preferences ----------------------------


def test_short_chord_is_not_truncated_under_default_preferences():
    beats = [
        gp_beat(
            _tick(0),
            [gp_note(1, 3), gp_note(2, 5)],
            duration_ticks=240,
        )
    ]
    song = gp_song(gp_track([gp_measure(beats)]))

    report = compute_eof_short_note_truncation_check(song, track_index=0, source_sha256="a" * 64)

    assert report.eof_truncated_count == 0
    assert report.truncation_matches_eof_preferences is True


def test_short_chord_is_truncated_when_chord_preference_is_explicitly_enabled():
    beats = [
        gp_beat(
            _tick(0),
            [gp_note(1, 3), gp_note(2, 5)],
            duration_ticks=240,
        )
    ]
    song = gp_song(gp_track([gp_measure(beats)]))

    report = compute_eof_short_note_truncation_check(
        song,
        track_index=0,
        source_sha256="a" * 64,
        truncate_short_chords=True,
    )

    assert report.eof_truncated_count == 2
    assert all(e.is_chord for m in report.mismatches for e in [m.event])


# --- Preferences can disable truncation entirely --------------------------------------------


def test_disabling_both_preferences_disables_all_truncation():
    beats = [gp_beat(_tick(0), [gp_note(1, 3, note_type="dead")], duration_ticks=240)]
    song = gp_song(gp_track([gp_measure(beats)]))

    report = compute_eof_short_note_truncation_check(
        song,
        track_index=0,
        source_sha256="a" * 64,
        truncate_short_notes=False,
        truncate_short_chords=False,
    )

    assert report.eof_truncated_count == 0
    assert report.truncation_matches_eof_preferences is True


# --- Provenance -------------------------------------------------------------------------


def test_report_records_upstream_provenance():
    beats = [gp_beat(_tick(0), [gp_note(1, 3)])]
    song = gp_song(gp_track([gp_measure(beats)]))

    report = compute_eof_short_note_truncation_check(song, track_index=0, source_sha256="a" * 64)

    assert report.upstream_repository == EOF_UPSTREAM_REPOSITORY == "raynebc/editor-on-fire"
    assert report.upstream_commit == EOF_UPSTREAM_COMMIT == "c0d88eabf7b00b0bd2cac9414df9fa9c6b3e7100"
    assert report.upstream_path == EOF_UPSTREAM_PATH == "src/gp_import.c"
    assert report.upstream_function == EOF_UPSTREAM_FUNCTION == "eof_load_gp"
    assert "short-note" in report.navigation_note


# --- Error handling ------------------------------------------------------------------------


def test_track_index_out_of_range_raises():
    song = gp_song(gp_track([gp_measure([gp_beat(_tick(0), [gp_note(1, 0)])])]))

    with pytest.raises(EOFShortNoteTruncationCheckError, match="track index"):
        compute_eof_short_note_truncation_check(song, track_index=5, source_sha256="a" * 64)


def test_no_measures_raises():
    song = gp_song(gp_track([]))

    with pytest.raises(EOFShortNoteTruncationCheckError, match="no measures"):
        compute_eof_short_note_truncation_check(song, track_index=0, source_sha256="a" * 64)


def test_negative_sustain_delta_tolerance_raises():
    song = gp_song(gp_track([gp_measure([gp_beat(_tick(0), [gp_note(1, 0)])])]))

    with pytest.raises(EOFShortNoteTruncationCheckError, match="tolerance"):
        compute_eof_short_note_truncation_check(
            song, track_index=0, source_sha256="a" * 64, sustain_delta_tolerance_seconds=-1.0
        )


def test_beats_with_no_notes_are_skipped():
    beats = [gp_beat(_tick(0), notes=[])]
    song = gp_song(gp_track([gp_measure(beats)]))

    report = compute_eof_short_note_truncation_check(song, track_index=0, source_sha256="a" * 64)

    assert report.note_count == 0
    assert "nothing to check" in report.reason


def test_zero_duration_beat_is_skipped():
    beats = [gp_beat(_tick(0), [gp_note(1, 0)], duration_ticks=0)]
    song = gp_song(gp_track([gp_measure(beats)]))

    report = compute_eof_short_note_truncation_check(song, track_index=0, source_sha256="a" * 64)

    assert report.note_count == 0
