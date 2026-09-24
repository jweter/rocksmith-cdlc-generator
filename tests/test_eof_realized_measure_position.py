import pytest

from rocksmith_cdlc_generator.eof_realized_measure_position import (
    realized_measure_positions,
    realized_measure_positions_from_markers,
    resolve_realized_measure,
)
from rocksmith_cdlc_generator.eof_repeat_unfolding import MeasureRepeatMarkers


def test_repeat_occurrences_have_distinct_realized_positions() -> None:
    sequence = [0, 1, 2, 0, 1, 3]

    positions = realized_measure_positions(sequence)

    assert [position.realized_measure_index for position in positions] == list(range(6))
    assert [(position.written_measure_index, position.occurrence) for position in positions] == [
        (0, 1),
        (1, 1),
        (2, 1),
        (0, 2),
        (1, 2),
        (3, 1),
    ]
    assert resolve_realized_measure(sequence, written_measure_index=0, occurrence=2) == positions[3]


def test_marker_bridge_uses_eof_unfolding_as_its_only_sequence_authority() -> None:
    markers = [
        MeasureRepeatMarkers(index=0, start_of_repeat=True, num_of_repeats=0, alt_ending_mask=0),
        MeasureRepeatMarkers(index=1, start_of_repeat=False, num_of_repeats=1, alt_ending_mask=0),
        MeasureRepeatMarkers(index=2, start_of_repeat=False, num_of_repeats=0, alt_ending_mask=0),
    ]

    positions = realized_measure_positions_from_markers(markers)

    assert [(item.written_measure_index, item.occurrence) for item in positions] == [
        (0, 1),
        (1, 1),
        (0, 2),
        (1, 2),
        (2, 1),
    ]


def test_missing_occurrence_fails_closed() -> None:
    assert resolve_realized_measure([0, 1, 0], written_measure_index=1, occurrence=2) is None


def test_invalid_indices_fail_closed() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        realized_measure_positions([0, -1])
    with pytest.raises(ValueError, match="non-negative"):
        resolve_realized_measure([0], written_measure_index=-1)
    with pytest.raises(ValueError, match="at least 1"):
        resolve_realized_measure([0], written_measure_index=0, occurrence=0)
