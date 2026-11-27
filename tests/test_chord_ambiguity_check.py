from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from rocksmith_cdlc_generator.chord_ambiguity_check import (
    DEFAULT_MIN_OVERLAP_S,
    assess_chord_ambiguity,
)


def _statuses(result: object) -> dict[str, str]:
    return {v.note_id: v.status for v in result.verdicts}  # type: ignore[attr-defined]


def test_sequential_notes_are_clear() -> None:
    result = assess_chord_ambiguity([("a", 0.0, 1.0), ("b", 1.0, 2.0), ("c", 3.0, 4.0)])

    assert result.status == "CLEAR"
    assert result.overlapping_count == 0
    assert set(_statuses(result).values()) == {"MONOPHONIC"}


def test_a_chord_stays_uncertain_without_isolation() -> None:
    result = assess_chord_ambiguity([("a", 0.0, 1.0), ("b", 0.0, 1.0), ("c", 2.0, 3.0)])

    assert result.status == "UNCERTAIN"
    assert _statuses(result) == {"a": "UNCERTAIN", "b": "UNCERTAIN", "c": "MONOPHONIC"}
    assert (result.overlapping_count, result.uncertain_count) == (2, 2)


def test_isolating_only_one_chord_note_leaves_the_other_uncertain() -> None:
    result = assess_chord_ambiguity([("a", 0.0, 1.0), ("b", 0.0, 1.0)], ["a"])

    assert result.status == "UNCERTAIN"
    assert _statuses(result) == {"a": "ISOLATED", "b": "UNCERTAIN"}
    assert result.uncertain_count == 1


def test_isolating_every_overlapping_note_is_isolated() -> None:
    result = assess_chord_ambiguity([("a", 0.0, 1.0), ("b", 0.5, 1.5), ("c", 4.0, 5.0)], {"a", "b"})

    assert result.status == "ISOLATED"
    assert _statuses(result) == {"a": "ISOLATED", "b": "ISOLATED", "c": "MONOPHONIC"}
    assert result.uncertain_count == 0


def test_isolating_a_monophonic_note_changes_nothing() -> None:
    result = assess_chord_ambiguity([("a", 0.0, 1.0), ("b", 2.0, 3.0)], ["a"])

    assert result.status == "CLEAR"
    assert _statuses(result) == {"a": "MONOPHONIC", "b": "MONOPHONIC"}


def test_a_long_note_overlapping_two_short_ones_flags_all_three() -> None:
    result = assess_chord_ambiguity([("long", 0.0, 4.0), ("s1", 0.5, 1.0), ("s2", 2.0, 2.5)])

    assert _statuses(result) == {"long": "UNCERTAIN", "s1": "UNCERTAIN", "s2": "UNCERTAIN"}


def test_notes_given_out_of_order_are_judged_the_same() -> None:
    result = assess_chord_ambiguity([("c", 5.0, 6.0), ("b", 0.5, 1.5), ("a", 0.0, 1.0)])

    assert _statuses(result) == {"a": "UNCERTAIN", "b": "UNCERTAIN", "c": "MONOPHONIC"}


def test_overlap_equal_to_the_threshold_does_not_count_but_just_above_does() -> None:
    at_limit = assess_chord_ambiguity([("a", 0.0, 1.0), ("b", 0.75, 1.5)], min_overlap_s=0.25)
    just_over = assess_chord_ambiguity([("a", 0.0, 1.0), ("b", 0.74, 1.5)], min_overlap_s=0.25)

    assert at_limit.status == "CLEAR"
    assert just_over.status == "UNCERTAIN"


def test_touching_notes_never_overlap_even_with_zero_threshold() -> None:
    assert assess_chord_ambiguity([("a", 0.0, 1.0), ("b", 1.0, 2.0)], min_overlap_s=0).status == "CLEAR"


def test_default_threshold_ignores_a_tiny_legato_overlap() -> None:
    gap = DEFAULT_MIN_OVERLAP_S / 2
    assert assess_chord_ambiguity([("a", 0.0, 1.0), ("b", 1.0 - gap, 2.0)]).status == "CLEAR"


@pytest.mark.parametrize(
    "notes, isolated, overlap, reason",
    [
        (None, (), 0.03, "NOTES_NOT_A_SEQUENCE"),
        ("abc", (), 0.03, "NOTES_NOT_A_SEQUENCE"),
        ([], (), 0.03, "NO_NOTES"),
        ([("a", 0.0)], (), 0.03, "NOTE_NOT_A_TRIPLE"),
        (["abc"], (), 0.03, "NOTE_NOT_A_TRIPLE"),
        ([("", 0.0, 1.0)], (), 0.03, "NOTE_ID_INVALID"),
        ([(1, 0.0, 1.0)], (), 0.03, "NOTE_ID_INVALID"),
        ([("a", 0.0, 1.0), ("a", 2.0, 3.0)], (), 0.03, "DUPLICATE_NOTE_ID"),
        ([("a", -1.0, 1.0)], (), 0.03, "NOTE_TIMES_INVALID"),
        ([("a", 1.0, 1.0)], (), 0.03, "NOTE_TIMES_INVALID"),
        ([("a", 2.0, 1.0)], (), 0.03, "NOTE_TIMES_INVALID"),
        ([("a", math.nan, 1.0)], (), 0.03, "NOTE_TIMES_INVALID"),
        ([("a", 0.0, math.inf)], (), 0.03, "NOTE_TIMES_INVALID"),
        ([("a", True, 1.0)], (), 0.03, "NOTE_TIMES_INVALID"),
        ([("a", 0.0, 1.0)], "a", 0.03, "ISOLATED_IDS_NOT_A_COLLECTION"),
        ([("a", 0.0, 1.0)], None, 0.03, "ISOLATED_IDS_NOT_A_COLLECTION"),
        ([("a", 0.0, 1.0)], [3], 0.03, "ISOLATED_ID_INVALID"),
        ([("a", 0.0, 1.0)], ["ghost"], 0.03, "ISOLATED_ID_UNKNOWN_NOTE"),
        ([("a", 0.0, 1.0)], (), -0.1, "MIN_OVERLAP_INVALID"),
        ([("a", 0.0, 1.0)], (), math.nan, "MIN_OVERLAP_INVALID"),
        ([("a", 0.0, 1.0)], (), True, "MIN_OVERLAP_INVALID"),
    ],
)
def test_invalid_input_is_reported_never_clear(
    notes: object, isolated: object, overlap: object, reason: str
) -> None:
    result = assess_chord_ambiguity(notes, isolated, overlap)

    assert result.status == "INVALID_INPUT"
    assert result.reason == reason
    assert result.verdicts == ()


def test_results_are_frozen() -> None:
    result = assess_chord_ambiguity([("a", 0.0, 1.0)])
    with pytest.raises(ValidationError):
        result.status = "UNCERTAIN"  # type: ignore[misc]
