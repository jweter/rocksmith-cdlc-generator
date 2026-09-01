from rocksmith_cdlc_generator.printed_notation_import import (
    PrintedNotationEvent,
    PrintedNotationFixture,
    PrintedNotationPage,
    PrintedNotationRestEvent,
)
from rocksmith_cdlc_generator.printed_notation_meter_validation import (
    validate_printed_notation_meter,
)


def _fixture(*, events, rests=()):
    return PrintedNotationFixture(
        instrument="bass",
        tuning_midi=[38, 45, 50, 55],
        bpm=80,
        pages=[PrintedNotationPage(page_number=2, events=list(events), rests=list(rests))],
    )


def test_full_measure_with_note_rest_coverage_is_valid() -> None:
    fixture = _fixture(
        events=[
            PrintedNotationEvent(measure=1, beat=1, duration_beats=1, string=0, fret=5),
            PrintedNotationEvent(measure=1, beat=3, duration_beats=2, string=1, fret=0),
        ],
        rests=[PrintedNotationRestEvent(measure=1, beat=2, duration_beats=1)],
    )
    assert validate_printed_notation_meter(fixture).valid


def test_chord_overlap_does_not_create_false_meter_error() -> None:
    fixture = _fixture(
        events=[
            PrintedNotationEvent(measure=1, beat=1, duration_beats=2, string=0, fret=5),
            PrintedNotationEvent(measure=1, beat=1, duration_beats=2, string=1, fret=3),
            PrintedNotationEvent(measure=1, beat=3, duration_beats=2, string=2, fret=0),
        ]
    )
    assert validate_printed_notation_meter(fixture).valid


def test_unexplained_gap_is_hard_issue() -> None:
    fixture = _fixture(
        events=[
            PrintedNotationEvent(measure=1, beat=1, duration_beats=1, string=0, fret=5),
            PrintedNotationEvent(measure=1, beat=3, duration_beats=2, string=1, fret=0),
        ]
    )
    report = validate_printed_notation_meter(fixture)
    assert not report.valid
    assert any(issue.code == "coverage_gap" for issue in report.issues)


def test_missing_measure_between_reviewed_measures_is_hard_issue() -> None:
    fixture = _fixture(
        events=[
            PrintedNotationEvent(measure=1, beat=1, duration_beats=4, string=0, fret=5),
            PrintedNotationEvent(measure=3, beat=1, duration_beats=4, string=1, fret=0),
        ]
    )
    report = validate_printed_notation_meter(fixture)
    assert any(
        issue.measure == 2 and issue.code == "missing_measure" for issue in report.issues
    )


def test_rest_note_overlap_is_hard_issue() -> None:
    fixture = _fixture(
        events=[
            PrintedNotationEvent(measure=1, beat=1, duration_beats=2, string=0, fret=5),
            PrintedNotationEvent(measure=1, beat=3, duration_beats=2, string=1, fret=0),
        ],
        rests=[PrintedNotationRestEvent(measure=1, beat=2, duration_beats=1)],
    )
    report = validate_printed_notation_meter(fixture)
    assert any(issue.code == "rest_note_overlap" for issue in report.issues)


def test_event_extending_beyond_measure_is_hard_issue() -> None:
    fixture = _fixture(
        events=[
            PrintedNotationEvent(measure=1, beat=1, duration_beats=5, string=0, fret=5),
        ]
    )
    report = validate_printed_notation_meter(fixture)
    assert any(issue.code == "event_outside_measure" for issue in report.issues)
