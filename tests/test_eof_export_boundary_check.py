from __future__ import annotations

from types import SimpleNamespace as NS

import pytest

from rocksmith_cdlc_generator.eof_export_boundary_check import (
    EOF_UPSTREAM_COMMIT,
    EOF_UPSTREAM_FUNCTION,
    EOF_UPSTREAM_PATH,
    EOF_UPSTREAM_PREFERENCE_PATH,
    EOF_UPSTREAM_REPOSITORY,
    EOFExportBoundaryCheckError,
    ExportedSourceNote,
    _exported_source_notes,
    _resolve_single_source_track_index,
    compute_eof_export_boundary_check,
)
from rocksmith_cdlc_generator.reviewed_export_events import ReviewedExportArrangement, ReviewedExportNote
from rocksmith_cdlc_generator.score_source import ArrangementRole

# --- Synthetic PyGuitarPro-shaped fixture helpers ---------------------------------------
#
# Mirrors the SimpleNamespace-based fixture convention used by
# tests/test_eof_rest_boundary_check.py and tests/test_eof_short_note_truncation_check.py:
# hand-built objects that duck-type the subset of PyGuitarPro's parsed Song/Track/Beat/Note/
# NoteEffect attributes this module reads, plus ``strings`` (read by guitarpro_import.
# _string_map, which neither of those two modules calls but this one does to recover pitch).
# No real Guitar Pro file, PyGuitarPro dependency, or commercial content is involved.

_QUARTER_TICKS = 960
_SHA = "a" * 64


def gp_string(number: int, open_midi: int):
    return NS(number=number, value=open_midi)


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


def gp_beat(start_tick: int, status_name: str = "normal", notes: list | None = None, duration_ticks: int = _QUARTER_TICKS):
    return NS(start=start_tick, status=NS(name=status_name), duration=NS(time=duration_ticks), notes=notes or [])


def gp_measure(beats: list):
    return NS(voices=[NS(beats=beats)])


def gp_track(measures: list, strings: list | None = None):
    return NS(measures=measures, strings=strings or [gp_string(1, 64), gp_string(2, 59)])


def gp_song(track, *, tempo: int = 120):
    return NS(tempo=tempo, tracks=[track])


def _tick(offset_from_zero: int) -> int:
    return _QUARTER_TICKS + offset_from_zero


# --- Explicit rest boundary side: materialized/exported notes ---------------------------


def test_no_rests_no_truncatable_notes_is_trivially_respected():
    beats = [gp_beat(_tick(0), "normal", [gp_note(1, 3)])]
    song = gp_song(gp_track([gp_measure(beats)]))
    exported = [
        ExportedSourceNote(
            source_event_index=0,
            source_track_index=0,
            source_start_seconds=0.5,
            source_duration_seconds=0.5,
            reviewed_start_seconds=0.5,
            reviewed_duration_seconds=0.5,
            midi=67,
            string_index=1,
            fret=3,
        )
    ]

    report = compute_eof_export_boundary_check(
        song,
        track_index=0,
        role=ArrangementRole.lead,
        exported_notes=exported,
        timing_points=[(0.0, 0.0), (10.0, 10.0)],
        source_sha256=_SHA,
    )

    assert report.explicit_rest_count == 0
    assert report.eof_truncatable_source_event_count == 0
    assert report.boundaries_respected is True
    assert report.truncation_matches_eof_preferences is True
    assert report.fully_determinable is True
    assert report.rest_violations == []
    assert report.truncation_mismatches == []


def test_materialized_sustain_stretched_across_rest_is_reported():
    # The registered score has a normal beat followed by an explicit rest; identity timing
    # means the projected rest occupies [0.5s, 1.0s) (one quarter note at 120bpm). A
    # materialized/exported note that keeps (or grows to) a 2.0s sustain from t=0 fully bleeds
    # into that rest even though nothing in this source track's own beat durations suggests it
    # should -- the exact "reconciliation stretched a sustain across a rest respected at import
    # time" defect shape item B names.
    beats = [
        gp_beat(_tick(0), "normal", [gp_note(1, 3)]),
        gp_beat(_tick(_QUARTER_TICKS), "rest"),
    ]
    song = gp_song(gp_track([gp_measure(beats)]))
    exported = [
        ExportedSourceNote(
            source_event_index=0,
            source_track_index=0,
            source_start_seconds=0.0,
            source_duration_seconds=0.5,
            reviewed_start_seconds=0.0,
            reviewed_duration_seconds=2.0,
            midi=67,
            string_index=1,
            fret=3,
        )
    ]

    report = compute_eof_export_boundary_check(
        song,
        track_index=0,
        role=ArrangementRole.lead,
        exported_notes=exported,
        timing_points=[(0.0, 0.0), (10.0, 10.0)],
        source_sha256=_SHA,
    )

    assert report.explicit_rest_count == 1
    assert report.boundaries_respected is False
    assert len(report.rest_violations) == 1
    violation = report.rest_violations[0]
    assert violation.overlap_seconds == pytest.approx(0.5, abs=1e-6)
    assert violation.rest_reviewed_start_seconds == pytest.approx(0.5, abs=1e-6)
    assert violation.rest_reviewed_end_seconds == pytest.approx(1.0, abs=1e-6)
    assert "overlap(s) found" in report.reason


def test_materialized_sustain_respecting_rest_after_scaled_timing_is_not_a_violation():
    # Reviewed timing doubles source time (2x). A source note ending exactly at the rest
    # boundary (0.5s) should map to a materialized note ending at 1.0s -- touching, not
    # overlapping, the doubled rest interval [1.0s, 2.0s).
    beats = [
        gp_beat(_tick(0), "normal", [gp_note(1, 3)]),
        gp_beat(_tick(_QUARTER_TICKS), "rest"),
    ]
    song = gp_song(gp_track([gp_measure(beats)]))
    exported = [
        ExportedSourceNote(
            source_event_index=0,
            source_track_index=0,
            source_start_seconds=0.0,
            source_duration_seconds=0.5,
            reviewed_start_seconds=0.0,
            reviewed_duration_seconds=1.0,
            midi=67,
            string_index=1,
            fret=3,
        )
    ]

    report = compute_eof_export_boundary_check(
        song,
        track_index=0,
        role=ArrangementRole.lead,
        exported_notes=exported,
        timing_points=[(0.0, 0.0), (10.0, 20.0)],
        source_sha256=_SHA,
    )

    assert report.boundaries_respected is True
    assert report.rest_violations == []


# --- Short-note/staccato/mute truncation side: materialized/exported notes ----------------


def test_export_failing_to_truncate_a_staccato_note_is_reported():
    beats = [
        gp_beat(
            _tick(0),
            "normal",
            [gp_note(1, 3, effect=gp_effect(staccato=True))],
            duration_ticks=_QUARTER_TICKS,
        )
    ]
    song = gp_song(gp_track([gp_measure(beats)]))
    # Same pitch/onset as the staccato source note, but reconciliation re-voiced it onto a
    # different physical string/fret and the exported sustain was never truncated.
    exported = [
        ExportedSourceNote(
            source_event_index=0,
            source_track_index=0,
            source_start_seconds=0.0,
            source_duration_seconds=0.5,
            reviewed_start_seconds=0.0,
            reviewed_duration_seconds=0.5,
            midi=67,
            string_index=9,
            fret=99,
        )
    ]

    report = compute_eof_export_boundary_check(
        song,
        track_index=0,
        role=ArrangementRole.bass,
        exported_notes=exported,
        timing_points=[(0.0, 0.0), (10.0, 10.0)],
        source_sha256=_SHA,
    )

    assert report.eof_truncatable_source_event_count == 1
    assert report.truncation_matches_eof_preferences is False
    assert report.unmatched_truncatable_source_event_count == 0
    assert len(report.truncation_mismatches) == 1
    mismatch = report.truncation_mismatches[0]
    assert mismatch.expected_reviewed_sustain_seconds == pytest.approx(0.001, abs=1e-6)
    assert mismatch.actual_reviewed_sustain_seconds == pytest.approx(0.5, abs=1e-6)
    assert "keep a longer materialized sustain" in report.reason


def test_export_correctly_truncating_a_staccato_note_matches():
    beats = [
        gp_beat(
            _tick(0),
            "normal",
            [gp_note(1, 3, effect=gp_effect(staccato=True))],
            duration_ticks=_QUARTER_TICKS,
        )
    ]
    song = gp_song(gp_track([gp_measure(beats)]))
    exported = [
        ExportedSourceNote(
            source_event_index=0,
            source_track_index=0,
            source_start_seconds=0.0,
            source_duration_seconds=0.5,
            reviewed_start_seconds=0.0,
            reviewed_duration_seconds=0.001,
            midi=67,
            string_index=1,
            fret=3,
        )
    ]

    report = compute_eof_export_boundary_check(
        song,
        track_index=0,
        role=ArrangementRole.lead,
        exported_notes=exported,
        timing_points=[(0.0, 0.0), (10.0, 10.0)],
        source_sha256=_SHA,
    )

    assert report.truncation_matches_eof_preferences is True
    assert report.truncation_mismatches == []
    assert report.fully_determinable is True


def test_unmatched_truncatable_note_is_reported_not_silently_skipped():
    # No exported note at all corresponds to this staccato source note -- e.g. Bass
    # reconciliation dropped it in favor of audio-only evidence. This must not silently pass.
    beats = [
        gp_beat(
            _tick(0),
            "normal",
            [gp_note(1, 3, effect=gp_effect(staccato=True))],
            duration_ticks=_QUARTER_TICKS,
        )
    ]
    song = gp_song(gp_track([gp_measure(beats)]))

    report = compute_eof_export_boundary_check(
        song,
        track_index=0,
        role=ArrangementRole.bass,
        exported_notes=[],
        timing_points=[(0.0, 0.0), (10.0, 10.0)],
        source_sha256=_SHA,
    )

    assert report.eof_truncatable_source_event_count == 1
    assert report.unmatched_truncatable_source_event_count == 1
    assert report.truncation_mismatches == []
    assert report.fully_determinable is False
    assert "could not be matched" in report.reason


def test_muted_note_truncation_is_evaluated_via_pitch_not_string_or_fret():
    beats = [gp_beat(_tick(0), "normal", [gp_note(1, 3, note_type="dead")], duration_ticks=4 * _QUARTER_TICKS)]
    song = gp_song(gp_track([gp_measure(beats)]))
    exported = [
        ExportedSourceNote(
            source_event_index=0,
            source_track_index=0,
            source_start_seconds=0.0,
            source_duration_seconds=2.0,
            reviewed_start_seconds=0.0,
            reviewed_duration_seconds=2.0,
            midi=67,
            string_index=None,
            fret=None,
        )
    ]

    report = compute_eof_export_boundary_check(
        song,
        track_index=0,
        role=ArrangementRole.bass,
        exported_notes=exported,
        timing_points=[(0.0, 0.0), (10.0, 10.0)],
        source_sha256=_SHA,
    )

    assert report.eof_truncatable_source_event_count == 1
    assert len(report.truncation_mismatches) == 1


# --- Validation / error handling -----------------------------------------------------------


def test_exported_note_from_a_different_track_raises():
    beats = [gp_beat(_tick(0), "normal", [gp_note(1, 0)])]
    song = gp_song(gp_track([gp_measure(beats)]))
    exported = [
        ExportedSourceNote(
            source_event_index=0,
            source_track_index=1,
            source_start_seconds=0.0,
            source_duration_seconds=0.5,
            reviewed_start_seconds=0.0,
            reviewed_duration_seconds=0.5,
            midi=64,
        )
    ]

    with pytest.raises(EOFExportBoundaryCheckError, match="single literal track"):
        compute_eof_export_boundary_check(
            song,
            track_index=0,
            role=ArrangementRole.lead,
            exported_notes=exported,
            timing_points=[(0.0, 0.0), (10.0, 10.0)],
            source_sha256=_SHA,
        )


def test_fewer_than_two_timing_points_raises():
    song = gp_song(gp_track([gp_measure([gp_beat(_tick(0), "normal", [gp_note(1, 0)])])]))

    with pytest.raises(EOFExportBoundaryCheckError, match="at least two"):
        compute_eof_export_boundary_check(
            song,
            track_index=0,
            role=ArrangementRole.lead,
            exported_notes=[],
            timing_points=[(0.0, 0.0)],
            source_sha256=_SHA,
        )


def test_non_increasing_reviewed_timing_raises():
    song = gp_song(gp_track([gp_measure([gp_beat(_tick(0), "normal", [gp_note(1, 0)])])]))

    with pytest.raises(EOFExportBoundaryCheckError, match="strictly increasing"):
        compute_eof_export_boundary_check(
            song,
            track_index=0,
            role=ArrangementRole.lead,
            exported_notes=[],
            timing_points=[(0.0, 5.0), (10.0, 1.0)],
            source_sha256=_SHA,
        )


def test_negative_tolerances_raise():
    song = gp_song(gp_track([gp_measure([gp_beat(_tick(0), "normal", [gp_note(1, 0)])])]))

    with pytest.raises(EOFExportBoundaryCheckError, match="overlap tolerance"):
        compute_eof_export_boundary_check(
            song,
            track_index=0,
            role=ArrangementRole.lead,
            exported_notes=[],
            timing_points=[(0.0, 0.0), (10.0, 10.0)],
            source_sha256=_SHA,
            overlap_tolerance_seconds=-1.0,
        )


def test_track_index_out_of_range_raises():
    song = gp_song(gp_track([gp_measure([gp_beat(_tick(0), "normal", [gp_note(1, 0)])])]))

    with pytest.raises(EOFExportBoundaryCheckError, match="track index"):
        compute_eof_export_boundary_check(
            song,
            track_index=5,
            role=ArrangementRole.lead,
            exported_notes=[],
            timing_points=[(0.0, 0.0), (10.0, 10.0)],
            source_sha256=_SHA,
        )


def test_report_records_upstream_provenance():
    song = gp_song(gp_track([gp_measure([gp_beat(_tick(0), "normal", [gp_note(1, 0)])])]))

    report = compute_eof_export_boundary_check(
        song,
        track_index=0,
        role=ArrangementRole.lead,
        exported_notes=[],
        timing_points=[(0.0, 0.0), (10.0, 10.0)],
        source_sha256=_SHA,
    )

    assert report.upstream_repository == EOF_UPSTREAM_REPOSITORY == "raynebc/editor-on-fire"
    assert report.upstream_commit == EOF_UPSTREAM_COMMIT == "c0d88eabf7b00b0bd2cac9414df9fa9c6b3e7100"
    assert report.upstream_path == EOF_UPSTREAM_PATH == "src/gp_import.c"
    assert report.upstream_function == EOF_UPSTREAM_FUNCTION == "eof_load_gp"
    assert report.upstream_preference_path == EOF_UPSTREAM_PREFERENCE_PATH == "src/main.c"
    assert "generated/exported" in report.navigation_note


# --- Composed multi-track resolution (pure helpers, no project I/O) ------------------------


def _export_note(
    *,
    source_event_index: int,
    composition_source_track_index: int | None = None,
    composition_source_event_index: int | None = None,
) -> ReviewedExportNote:
    return ReviewedExportNote(
        source_event_index=source_event_index,
        source_start_seconds=float(source_event_index),
        source_duration_seconds=0.5,
        reviewed_start_seconds=float(source_event_index),
        reviewed_duration_seconds=0.5,
        midi=64,
        string_index=0,
        fret=0,
        import_confidence=1.0,
        trust_class="symbolic_verified",
        position_ready=True,
        composition_source_track_index=composition_source_track_index,
        composition_source_event_index=composition_source_event_index,
    )


def _arrangement(notes: list[ReviewedExportNote], *, source_track_index: int = 0) -> ReviewedExportArrangement:
    return ReviewedExportArrangement(
        role=ArrangementRole.lead,
        source_track_index=source_track_index,
        source_output_json="fanout/lead.json",
        source_output_sha256=_SHA,
        recording_sha256=_SHA,
        score_sha256=_SHA,
        tuning_midi=None,
        notes=notes,
        chord_groups=[],
    )


def test_resolve_single_track_without_composition_uses_source_track_index():
    arrangement = _arrangement([_export_note(source_event_index=0), _export_note(source_event_index=1)])

    assert _resolve_single_source_track_index(arrangement) == 0


def test_resolve_single_track_with_uniform_composition_index():
    arrangement = _arrangement(
        [
            _export_note(source_event_index=0, composition_source_track_index=2, composition_source_event_index=0),
            _export_note(source_event_index=1, composition_source_track_index=2, composition_source_event_index=1),
        ]
    )

    assert _resolve_single_source_track_index(arrangement) == 2


def test_resolve_composed_multi_track_raises():
    arrangement = _arrangement(
        [
            _export_note(source_event_index=0, composition_source_track_index=2, composition_source_event_index=0),
            _export_note(source_event_index=1, composition_source_track_index=3, composition_source_event_index=0),
        ]
    )

    with pytest.raises(EOFExportBoundaryCheckError, match="composed multi-track"):
        _resolve_single_source_track_index(arrangement)


def test_exported_source_notes_projects_composition_event_index():
    arrangement = _arrangement(
        [_export_note(source_event_index=5, composition_source_track_index=2, composition_source_event_index=1)]
    )

    notes = _exported_source_notes(arrangement, 2)

    assert len(notes) == 1
    assert notes[0].source_event_index == 1
    assert notes[0].source_track_index == 2
    assert notes[0].midi == 64
