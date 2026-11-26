from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from rocksmith_cdlc_generator.phantom_sustain_check import (
    DEFAULT_TOLERANCE_S,
    check_phantom_sustain,
)


def test_notes_that_stop_before_the_gap_are_clear() -> None:
    result = check_phantom_sustain([(1.0, 0.5), (3.0, 0.25)], [(2.0, 3.0)])

    assert result.status == "CLEAR"
    assert result.flagged == ()


def test_note_sustaining_into_a_gap_is_flagged_with_its_overlap() -> None:
    result = check_phantom_sustain([(1.0, 2.0)], [(2.0, 4.0)], tolerance_s=0.25)

    assert result.status == "PHANTOM_SUSTAIN"
    assert result.reason == "SUSTAIN_THROUGH_SILENCE"
    assert [(f.note_index, f.overlap_s) for f in result.flagged] == [(0, 1.0)]


def test_overlap_equal_to_the_tolerance_is_not_flagged() -> None:
    # 1.0 + 0.5 = 1.5; the gap starts at 1.25; overlap is exactly 0.25.
    result = check_phantom_sustain([(1.0, 0.5)], [(1.25, 5.0)], tolerance_s=0.25)

    assert result.status == "CLEAR"


def test_overlap_just_above_the_tolerance_is_flagged() -> None:
    result = check_phantom_sustain([(1.0, 0.75)], [(1.25, 5.0)], tolerance_s=0.25)

    assert result.status == "PHANTOM_SUSTAIN"
    assert result.flagged[0].overlap_s == 0.5


def test_note_spanning_a_whole_gap_overlaps_by_the_gap_length() -> None:
    result = check_phantom_sustain([(0.0, 10.0)], [(2.0, 3.0)], tolerance_s=0.25)

    assert [f.overlap_s for f in result.flagged] == [1.0]


def test_largest_overlap_across_several_gaps_is_reported() -> None:
    result = check_phantom_sustain(
        [(0.0, 10.0)], [(1.0, 1.5), (3.0, 5.0), (7.0, 7.25)], tolerance_s=0.25
    )

    assert [f.overlap_s for f in result.flagged] == [2.0]


def test_gap_that_starts_at_or_before_the_note_is_not_judged_here() -> None:
    result = check_phantom_sustain([(2.0, 1.0)], [(1.0, 5.0), (2.0, 4.0)], tolerance_s=0.0)

    assert result.status == "CLEAR"


def test_only_the_offending_notes_are_flagged() -> None:
    result = check_phantom_sustain(
        [(0.0, 0.5), (1.0, 3.0), (6.0, 0.25)], [(2.0, 4.0)], tolerance_s=0.25
    )

    assert [f.note_index for f in result.flagged] == [1]


def test_no_gaps_or_no_notes_is_clear() -> None:
    assert check_phantom_sustain([(1.0, 1.0)], []).status == "CLEAR"
    assert check_phantom_sustain([], [(1.0, 2.0)]).status == "CLEAR"


def test_default_tolerance_is_used_when_omitted() -> None:
    assert DEFAULT_TOLERANCE_S == 0.05
    assert check_phantom_sustain([(1.0, 1.25)], [(2.0, 3.0)]).status == "PHANTOM_SUSTAIN"
    assert check_phantom_sustain([(1.0, 0.03125)], [(1.0078125, 3.0)]).status == "CLEAR"


@pytest.mark.parametrize(
    "bad_notes",
    [
        [(math.nan, 1.0)],
        [(1.0, math.inf)],
        [(-1.0, 1.0)],
        [(1.0, -0.5)],
        [(True, 1.0)],
        [(1.0, False)],
        [(1.0,)],
        [(1.0, 2.0, 3.0)],
        ["ab"],
        "notes",
        None,
        42,
    ],
)
def test_invalid_notes_are_reported_not_passed(bad_notes: object) -> None:
    result = check_phantom_sustain(bad_notes, [(2.0, 3.0)])

    assert result.status == "INVALID_INPUT"
    assert result.reason == "INVALID_NOTES"
    assert result.flagged == ()


@pytest.mark.parametrize(
    "bad_gaps",
    [
        [(2.0, 2.0)],
        [(3.0, 2.0)],
        [(-1.0, 2.0)],
        [(math.nan, 2.0)],
        [(2.0, math.inf)],
        [(True, 3.0)],
        [(2.0,)],
        "gaps",
        None,
    ],
)
def test_invalid_gaps_are_reported_not_passed(bad_gaps: object) -> None:
    result = check_phantom_sustain([(1.0, 1.0)], bad_gaps)

    assert result.status == "INVALID_INPUT"
    assert result.reason == "INVALID_GAPS"


@pytest.mark.parametrize("bad_tolerance", [-0.01, math.nan, math.inf, True, "0.05", None])
def test_invalid_tolerance_is_reported(bad_tolerance: object) -> None:
    result = check_phantom_sustain([(1.0, 1.0)], [(2.0, 3.0)], bad_tolerance)

    assert result.status == "INVALID_INPUT"
    assert result.reason == "INVALID_TOLERANCE"


def test_result_is_immutable() -> None:
    result = check_phantom_sustain([(1.0, 2.0)], [(2.0, 4.0)], tolerance_s=0.25)
    with pytest.raises(ValidationError):
        result.status = "CLEAR"  # type: ignore[misc]
