from __future__ import annotations

from rocksmith_cdlc_generator.guitar_authoring import (
    GuitarAuthoringChart,
    GuitarAuthoringNote,
    GuitarChordEvent,
)
from rocksmith_cdlc_generator.shared_guitar_bounds import _bound_chart
from rocksmith_cdlc_generator.source_import import SourceTrustClass


def _note(start: float, duration: float, *, string: int, fret: int) -> GuitarAuthoringNote:
    return GuitarAuthoringNote(
        start_seconds=start,
        duration_seconds=duration,
        midi=(40, 45, 50, 55, 59, 64)[string] + fret,
        string_index=string,
        fret=fret,
        trust_class=SourceTrustClass.symbolic_verified,
    )


def test_shared_guitar_boundary_omits_trailing_events_and_clips_sustains() -> None:
    duration = 10.0
    crossing_single = _note(9.75, 1.0, string=0, fret=3)
    trailing_single = _note(10.25, 0.5, string=1, fret=2)
    chord_notes = [
        _note(9.8, 0.8, string=0, fret=5),
        _note(9.8, 0.8, string=1, fret=7),
        _note(9.8, 0.8, string=2, fret=7),
    ]
    trailing_chord_notes = [
        _note(10.4, 0.5, string=0, fret=5),
        _note(10.4, 0.5, string=1, fret=7),
    ]
    chart = GuitarAuthoringChart(
        arrangement="rhythm",
        source_sha256="a" * 64,
        alignment_confidence=1.0,
        tuning_midi=(40, 45, 50, 55, 59, 64),
        single_notes=[crossing_single, trailing_single],
        chords=[
            GuitarChordEvent(
                start_seconds=9.8,
                sustain_seconds=0.8,
                chord_id=0,
                shape=(5, 7, 7, -1, -1, -1),
                notes=chord_notes,
            ),
            GuitarChordEvent(
                start_seconds=10.4,
                sustain_seconds=0.5,
                chord_id=1,
                shape=(5, 7, -1, -1, -1, -1),
                notes=trailing_chord_notes,
            ),
        ],
    )

    bounded, report = _bound_chart(chart, duration)

    assert len(bounded.single_notes) == 1
    assert bounded.single_notes[0].start_seconds + bounded.single_notes[0].duration_seconds <= duration
    assert len(bounded.chords) == 1
    assert bounded.chords[0].start_seconds + bounded.chords[0].sustain_seconds <= duration
    assert all(
        note.start_seconds + note.duration_seconds <= duration
        for note in bounded.chords[0].notes
    )
    assert report.omitted_single_notes == 1
    assert report.omitted_chords == 1
    assert report.clipped_single_notes == 1
    assert report.clipped_chords == 1
    assert report.clipped_chord_notes == 3
    assert any(message.startswith("Recording boundary:") for message in bounded.warnings)


def test_shared_guitar_boundary_is_noop_for_in_bounds_chart() -> None:
    chart = GuitarAuthoringChart(
        arrangement="lead",
        source_sha256="b" * 64,
        alignment_confidence=1.0,
        tuning_midi=(40, 45, 50, 55, 59, 64),
        single_notes=[_note(1.0, 0.5, string=5, fret=3)],
    )

    bounded, report = _bound_chart(chart, 10.0)

    assert bounded == chart
    assert report.omitted_single_notes == 0
    assert report.omitted_chords == 0
    assert report.clipped_single_notes == 0
    assert report.clipped_chords == 0
    assert report.clipped_chord_notes == 0
