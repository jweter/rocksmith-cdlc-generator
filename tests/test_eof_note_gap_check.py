import pytest

from rocksmith_cdlc_generator.eof_note_gap_check import (
    EOFNoteGapCheckError,
    compute_eof_note_gap_check,
)
from rocksmith_cdlc_generator.reviewed_export_events import (
    ReviewedExportArrangement,
    ReviewedExportNote,
)
from rocksmith_cdlc_generator.score_source import ArrangementRole
from rocksmith_cdlc_generator.source_import import SourceTrustClass

_SHA = "ab" * 32


def _note(
    *,
    index: int,
    start: float,
    duration: float,
    string_index: int | None,
    techniques: list[str] | None = None,
) -> ReviewedExportNote:
    return ReviewedExportNote(
        source_event_index=index,
        source_start_seconds=start,
        source_duration_seconds=duration,
        reviewed_start_seconds=start,
        reviewed_duration_seconds=duration,
        midi=40,
        string_index=string_index,
        fret=0 if string_index is not None else None,
        techniques=techniques or [],
        import_confidence=1.0,
        trust_class=SourceTrustClass.symbolic_verified,
        position_ready=string_index is not None,
    )


def _arrangement(notes: list[ReviewedExportNote], *, role: ArrangementRole = ArrangementRole.lead) -> ReviewedExportArrangement:
    return ReviewedExportArrangement(
        role=role,
        source_track_index=0,
        source_output_json="sources/fanout/lead.json",
        source_output_sha256=_SHA,
        recording_sha256=_SHA,
        score_sha256=_SHA,
        notes=notes,
    )


def test_no_notes_is_trivially_respected() -> None:
    report = compute_eof_note_gap_check(_arrangement([]))
    assert report.gaps_respected is True
    assert "nothing to check" in report.reason


def test_non_overlapping_same_string_notes_pass() -> None:
    arrangement = _arrangement(
        [
            _note(index=0, start=0.0, duration=0.5, string_index=1),
            _note(index=1, start=1.0, duration=0.5, string_index=1),
        ]
    )
    report = compute_eof_note_gap_check(arrangement)
    assert report.gaps_respected is True
    assert report.violations == []


def test_note_touching_next_note_exactly_is_not_a_violation() -> None:
    arrangement = _arrangement(
        [
            _note(index=0, start=0.0, duration=1.0, string_index=1),
            _note(index=1, start=1.0, duration=0.5, string_index=1),
        ]
    )
    report = compute_eof_note_gap_check(arrangement)
    assert report.gaps_respected is True


def test_same_string_overlap_is_flagged() -> None:
    arrangement = _arrangement(
        [
            _note(index=0, start=0.0, duration=1.5, string_index=2),
            _note(index=1, start=1.0, duration=0.5, string_index=2),
        ]
    )
    report = compute_eof_note_gap_check(arrangement)
    assert report.gaps_respected is False
    assert len(report.violations) == 1
    violation = report.violations[0]
    assert violation.string_index == 2
    assert violation.note_source_event_index == 0
    assert violation.next_note_source_event_index == 1
    assert violation.overlap_seconds == pytest.approx(0.5)


def test_different_string_overlap_is_not_flagged() -> None:
    # A chord: two strings sounding at the same time is legitimate, never a gap violation.
    arrangement = _arrangement(
        [
            _note(index=0, start=0.0, duration=1.0, string_index=1),
            _note(index=1, start=0.0, duration=1.0, string_index=2),
        ]
    )
    report = compute_eof_note_gap_check(arrangement)
    assert report.gaps_respected is True


def test_tied_continuation_note_is_excluded_from_the_pair_it_closes() -> None:
    arrangement = _arrangement(
        [
            _note(index=0, start=0.0, duration=1.5, string_index=1),
            _note(index=1, start=1.0, duration=0.5, string_index=1, techniques=["tie"]),
        ]
    )
    report = compute_eof_note_gap_check(arrangement)
    assert report.gaps_respected is True


def test_position_not_ready_notes_are_excluded() -> None:
    arrangement = _arrangement(
        [
            _note(index=0, start=0.0, duration=1.5, string_index=None),
            _note(index=1, start=1.0, duration=0.5, string_index=None),
        ]
    )
    report = compute_eof_note_gap_check(arrangement)
    assert report.gaps_respected is True
    assert report.position_ready_note_count == 0


def test_negative_touch_tolerance_is_rejected() -> None:
    with pytest.raises(EOFNoteGapCheckError):
        compute_eof_note_gap_check(_arrangement([]), touch_tolerance_seconds=-1.0)
