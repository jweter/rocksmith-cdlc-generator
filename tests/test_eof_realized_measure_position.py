import pytest

from rocksmith_cdlc_generator.eof_realized_measure_position import (
    realized_measure_positions,
    resolve_realized_measure,
)


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


def test_missing_occurrence_fails_closed() -> None:
    assert resolve_realized_measure([0, 1, 0], written_measure_index=1, occurrence=2) is None


def test_invalid_indices_fail_closed() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        realized_measure_positions([0, -1])
    with pytest.raises(ValueError, match="non-negative"):
        resolve_realized_measure([0], written_measure_index=-1)
    with pytest.raises(ValueError, match="at least 1"):
        resolve_realized_measure([0], written_measure_index=0, occurrence=0)
