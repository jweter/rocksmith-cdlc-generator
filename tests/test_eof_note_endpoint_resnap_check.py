import pytest

from rocksmith_cdlc_generator.eof_note_endpoint_resnap_check import (
    EOFNoteEndpointResnapCheckError,
    compute_eof_note_endpoint_resnap_check,
)
from rocksmith_cdlc_generator.source_import import (
    ImportedSource,
    SourceNoteEvent,
    SourceProvenance,
    SourceTrack,
)

_SHA = "ab" * 32


def _source(*, beat_times: list[float], notes: list[SourceNoteEvent]) -> ImportedSource:
    return ImportedSource(
        provenance=SourceProvenance(
            source_type="gp5",
            source_filename="song.gp5",
            source_sha256=_SHA,
            importer="pyguitarpro-adapter",
            importer_version="1",
        ),
        beat_times_seconds=beat_times,
        tracks=[
            SourceTrack(source_track_index=0, instrument="bass", notes=notes),
        ],
    )


def _note(start: float, duration: float) -> SourceNoteEvent:
    return SourceNoteEvent(start_seconds=start, duration_seconds=duration, midi=40, import_confidence=1.0)


def test_endpoint_exactly_on_grid_is_not_flagged() -> None:
    source = _source(beat_times=[0.0, 0.5, 1.0], notes=[_note(0.0, 0.5)])
    report = compute_eof_note_endpoint_resnap_check(source)
    assert report.endpoints_are_grid_aligned is True
    assert report.candidates == []


def test_endpoint_within_rounding_drift_is_flagged() -> None:
    # Ends at 0.4995s, ~0.5ms shy of the 0.5s grid line -- the exact class of
    # tick/ms floating-point rounding drift EOF's resnap pass targets.
    source = _source(beat_times=[0.0, 0.5, 1.0], notes=[_note(0.0, 0.4995)])
    report = compute_eof_note_endpoint_resnap_check(source)
    assert report.endpoints_are_grid_aligned is False
    assert len(report.candidates) == 1
    candidate = report.candidates[0]
    assert candidate.track_index == 0
    assert candidate.note_index == 0
    assert candidate.nearest_grid_seconds == pytest.approx(0.5)
    assert candidate.drift_seconds == pytest.approx(0.0005, abs=1e-6)


def test_endpoint_far_from_grid_is_not_flagged_as_drift() -> None:
    # A real 100ms gap is a musical fact, not a rounding artifact -- must not be flagged.
    source = _source(beat_times=[0.0, 0.5, 1.0], notes=[_note(0.0, 0.4)])
    report = compute_eof_note_endpoint_resnap_check(source)
    assert report.endpoints_are_grid_aligned is True
    assert report.candidates == []


def test_empty_beat_grid_has_nothing_to_check() -> None:
    source = _source(beat_times=[], notes=[_note(0.0, 0.5)])
    report = compute_eof_note_endpoint_resnap_check(source)
    assert report.endpoints_are_grid_aligned is True
    assert "nothing to check" in report.reason


def test_multiple_tracks_and_notes_are_all_checked() -> None:
    source = ImportedSource(
        provenance=SourceProvenance(
            source_type="gp5",
            source_filename="song.gp5",
            source_sha256=_SHA,
            importer="pyguitarpro-adapter",
            importer_version="1",
        ),
        beat_times_seconds=[0.0, 0.5, 1.0, 1.5],
        tracks=[
            SourceTrack(
                source_track_index=0,
                instrument="bass",
                notes=[_note(0.0, 0.4995), _note(0.5, 0.5)],
            ),
            SourceTrack(
                source_track_index=1,
                instrument="lead",
                notes=[_note(1.0, 0.5005)],
            ),
        ],
    )
    report = compute_eof_note_endpoint_resnap_check(source)
    assert report.note_count == 3
    assert len(report.candidates) == 2
    assert {(c.track_index, c.note_index) for c in report.candidates} == {(0, 0), (1, 0)}


def test_invalid_tolerance_ordering_is_rejected() -> None:
    source = _source(beat_times=[0.0, 0.5], notes=[_note(0.0, 0.5)])
    with pytest.raises(EOFNoteEndpointResnapCheckError):
        compute_eof_note_endpoint_resnap_check(
            source, drift_tolerance_seconds=1e-6, exact_tolerance_seconds=1e-6
        )
