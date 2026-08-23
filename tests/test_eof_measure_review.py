from __future__ import annotations

from rocksmith_cdlc_generator.eof_measure_review import (
    build_measure_windows,
    measure_index_for_time,
    notes_for_measure,
    summarize_measure_fingering,
)
from rocksmith_cdlc_generator.song_preview import (
    PreviewArrangement,
    PreviewNoteEvent,
    SongPreviewSnapshot,
)
from rocksmith_cdlc_generator.source_import import SourceTimeSignatureEvent, SourceTrustClass


def _note(index: int, when: float, *, string: int | None, fret: int | None, review: bool = False):
    return PreviewNoteEvent(
        event_index=index,
        start_seconds=when,
        duration_seconds=0.25,
        midi=40 + index,
        note_name=None,
        string_index=string,
        fret=fret,
        techniques=[],
        import_confidence=1.0,
        trust_class=SourceTrustClass.symbolic_verified,
        review_required=review,
    )


def _snapshot() -> SongPreviewSnapshot:
    arrangement = PreviewArrangement(
        instrument="bass",
        part_index=2,
        part_id="track-2",
        part_name="Bass",
        source_track_name="Bass",
        tuning_midi=[28, 33, 38, 43],
        output_json="sources/imported/bass.json",
        note_count=5,
        notes=[
            _note(0, 0.20, string=0, fret=0),
            _note(1, 1.10, string=1, fret=5),
            _note(2, 2.20, string=2, fret=7, review=True),
            _note(3, 4.10, string=3, fret=9),
            _note(4, 4.30, string=None, fret=None),
        ],
    )
    signatures = [
        SourceTimeSignatureEvent(tick=0, time_seconds=0.0, numerator=4, denominator=4),
        SourceTimeSignatureEvent(tick=3840, time_seconds=2.0, numerator=4, denominator=4),
        SourceTimeSignatureEvent(tick=7680, time_seconds=4.0, numerator=3, denominator=4),
    ]
    return SongPreviewSnapshot(
        source_filename="synthetic.gp5",
        source_sha256="a" * 64,
        beat_times_seconds=[],
        tempo_events=[],
        time_signatures=signatures,
        arrangements=[arrangement],
    )


def test_measure_windows_use_gp_measure_header_times() -> None:
    measures = build_measure_windows(_snapshot())

    assert [(item.number, item.start_seconds, item.end_seconds) for item in measures] == [
        (1, 0.0, 2.0),
        (2, 2.0, 4.0),
        (3, 4.0, 4.55),
    ]
    assert measures[2].numerator == 3
    assert measures[2].denominator == 4


def test_measure_navigation_is_deterministic_at_boundaries() -> None:
    measures = build_measure_windows(_snapshot())

    assert measure_index_for_time(measures, 0.0) == 0
    assert measure_index_for_time(measures, 1.999) == 0
    assert measure_index_for_time(measures, 2.0) == 1
    assert measure_index_for_time(measures, 4.0) == 2
    assert measure_index_for_time(measures, 99.0) == 2


def test_measure_fret_summary_preserves_observed_positions_without_optimizing() -> None:
    snapshot = _snapshot()
    measures = build_measure_windows(snapshot)
    arrangement = snapshot.arrangements[0]

    first = summarize_measure_fingering(arrangement, measures[0])
    assert first.event_count == 2
    assert first.active_strings == (1, 2)
    assert first.open_string_count == 1
    assert first.min_fret == 5
    assert first.max_fret == 5
    assert first.review_required_count == 0

    third = summarize_measure_fingering(arrangement, measures[2])
    assert third.event_count == 2
    assert third.active_strings == (4,)
    assert third.min_fret == 9
    assert third.max_fret == 9
    assert third.unresolved_position_count == 1


def test_notes_for_measure_uses_onset_ownership() -> None:
    snapshot = _snapshot()
    measures = build_measure_windows(snapshot)
    arrangement = snapshot.arrangements[0]

    assert [item.event_index for item in notes_for_measure(arrangement, measures[1])] == [2]
