from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from rocksmith_cdlc_generator.harmonic_confusion_check import (
    classify_harmonic_confusion,
    summarize_harmonic_confusion,
)

E2 = 82.41  # low E on a guitar


def _cents(hz: float, cents: float) -> float:
    return hz * 2 ** (cents / 1200.0)


def test_exact_pitch_is_a_match() -> None:
    result = classify_harmonic_confusion(E2, E2)

    assert result.status == "MATCH"
    assert result.harmonic_number == 1
    assert result.direction == "none"
    assert result.cents_error == pytest.approx(0.0, abs=1e-9)


def test_small_detuning_still_matches() -> None:
    assert classify_harmonic_confusion(E2, _cents(E2, 30)).status == "MATCH"


@pytest.mark.parametrize("factor", [2, 4, 8])
def test_octaves_up_are_octave_errors(factor: int) -> None:
    result = classify_harmonic_confusion(E2, E2 * factor)

    assert result.status == "OCTAVE_ERROR"
    assert result.harmonic_number == factor
    assert result.direction == "up"


@pytest.mark.parametrize("factor", [2, 4, 8])
def test_octaves_down_are_octave_errors(factor: int) -> None:
    result = classify_harmonic_confusion(E2, E2 / factor)

    assert result.status == "OCTAVE_ERROR"
    assert result.direction == "down"
    assert result.harmonic_number == factor


@pytest.mark.parametrize("factor", [3, 5, 6, 7])
def test_other_harmonics_are_harmonic_errors(factor: int) -> None:
    up = classify_harmonic_confusion(E2, E2 * factor)
    down = classify_harmonic_confusion(E2, E2 / factor)

    assert (up.status, up.direction, up.harmonic_number) == ("HARMONIC_ERROR", "up", factor)
    assert (down.status, down.direction) == ("HARMONIC_ERROR", "down")


def test_a_pitch_between_harmonics_is_an_unrelated_mismatch() -> None:
    # Halfway (in cents) between x1 and x2: 600 cents above the expected note.
    result = classify_harmonic_confusion(E2, _cents(E2, 600))

    assert result.status == "MISMATCH"
    assert result.reason == "NOT_A_HARMONIC_RELATION"
    assert result.harmonic_number is None


def test_tolerance_boundary_inside_and_outside() -> None:
    assert classify_harmonic_confusion(E2, _cents(E2 * 2, 49), 50).status == "OCTAVE_ERROR"
    assert classify_harmonic_confusion(E2, _cents(E2 * 2, 60), 50).status == "MISMATCH"


def test_tighter_tolerance_changes_the_verdict() -> None:
    detected = _cents(E2, 30)
    assert classify_harmonic_confusion(E2, detected, 50).status == "MATCH"
    assert classify_harmonic_confusion(E2, detected, 10).status == "MISMATCH"


def test_widest_allowed_tolerance_is_never_ambiguous() -> None:
    # x8 and x7 are 231 cents apart, so +/-100 cents resolves to one candidate each.
    assert classify_harmonic_confusion(E2, _cents(E2 * 8, 99.9), 100).harmonic_number == 8
    assert classify_harmonic_confusion(E2, _cents(E2 * 7, -99.9), 100).harmonic_number == 7


@pytest.mark.parametrize(
    "expected, detected, tolerance, reason",
    [
        (0, E2, 50, "EXPECTED_NOT_POSITIVE_NUMBER"),
        (-5.0, E2, 50, "EXPECTED_NOT_POSITIVE_NUMBER"),
        (math.nan, E2, 50, "EXPECTED_NOT_POSITIVE_NUMBER"),
        (True, E2, 50, "EXPECTED_NOT_POSITIVE_NUMBER"),
        ("82", E2, 50, "EXPECTED_NOT_POSITIVE_NUMBER"),
        (None, E2, 50, "EXPECTED_NOT_POSITIVE_NUMBER"),
        (E2, 0, 50, "DETECTED_NOT_POSITIVE_NUMBER"),
        (E2, math.inf, 50, "DETECTED_NOT_POSITIVE_NUMBER"),
        (E2, False, 50, "DETECTED_NOT_POSITIVE_NUMBER"),
        (E2, E2, 0, "TOLERANCE_OUT_OF_RANGE"),
        (E2, E2, -1, "TOLERANCE_OUT_OF_RANGE"),
        (E2, E2, 101, "TOLERANCE_OUT_OF_RANGE"),
        (E2, E2, math.nan, "TOLERANCE_OUT_OF_RANGE"),
        (E2, E2, True, "TOLERANCE_OUT_OF_RANGE"),
    ],
)
def test_invalid_input_is_reported_never_a_match(
    expected: object, detected: object, tolerance: object, reason: str
) -> None:
    result = classify_harmonic_confusion(expected, detected, tolerance)

    assert result.status == "INVALID_INPUT"
    assert result.reason == reason


def test_results_are_frozen() -> None:
    result = classify_harmonic_confusion(E2, E2)
    with pytest.raises(ValidationError):
        result.status = "MISMATCH"  # type: ignore[misc]


# ------------------------------------------------------------------ summary


def test_summary_is_clear_only_when_every_pair_matches() -> None:
    summary = summarize_harmonic_confusion([E2, 110.0], [E2, 110.0])

    assert summary.status == "CLEAR"
    assert (summary.total, summary.matches, summary.confusion_rate) == (2, 2, 0.0)


def test_summary_counts_each_kind_of_error() -> None:
    expected = [E2, E2, E2, E2]
    detected = [E2, E2 * 2, E2 * 3, _cents(E2, 600)]
    summary = summarize_harmonic_confusion(expected, detected)

    assert summary.status == "CONFUSION_FOUND"
    assert (summary.matches, summary.octave_errors, summary.harmonic_errors, summary.mismatches) == (
        1,
        1,
        1,
        1,
    )
    assert summary.confusion_rate == pytest.approx(0.75)


@pytest.mark.parametrize(
    "expected, detected, reason",
    [
        ([E2], [E2, E2], "LENGTH_MISMATCH"),
        ([], [], "EMPTY"),
        ("abc", [E2], "NOT_A_SEQUENCE"),
        ([E2], None, "NOT_A_SEQUENCE"),
        ([E2, 0.0], [E2, E2], "EXPECTED_NOT_POSITIVE_NUMBER"),
        ([E2, E2], [E2, math.nan], "DETECTED_NOT_POSITIVE_NUMBER"),
    ],
)
def test_summary_invalid_input_never_reports_clear(
    expected: object, detected: object, reason: str
) -> None:
    summary = summarize_harmonic_confusion(expected, detected)

    assert summary.status == "INVALID_INPUT"
    assert summary.reason == reason
