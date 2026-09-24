from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RealizedMeasurePosition:
    """One EOF-style realized playback location for a written measure."""

    realized_measure_index: int
    written_measure_index: int
    occurrence: int


def realized_measure_positions(sequence: list[int]) -> tuple[RealizedMeasurePosition, ...]:
    """Index an EOF-unfolded measure sequence without inventing timing authority.

    ``sequence`` is the output of ``eof_repeat_unfolding.unfold_measure_sequence``.
    Repeated written measures receive distinct realized positions and monotonically
    increasing occurrence numbers. Negative written-measure indices fail closed.
    """
    occurrences: dict[int, int] = {}
    positions: list[RealizedMeasurePosition] = []
    for realized_index, written_index in enumerate(sequence):
        if written_index < 0:
            raise ValueError("written measure index must be non-negative")
        occurrence = occurrences.get(written_index, 0) + 1
        occurrences[written_index] = occurrence
        positions.append(
            RealizedMeasurePosition(
                realized_measure_index=realized_index,
                written_measure_index=written_index,
                occurrence=occurrence,
            )
        )
    return tuple(positions)


def resolve_realized_measure(
    sequence: list[int], *, written_measure_index: int, occurrence: int = 1
) -> RealizedMeasurePosition | None:
    """Resolve one authored measure occurrence onto EOF's realized playback order.

    Returns ``None`` when the requested written measure/occurrence is absent rather
    than guessing a neighboring bar. This is advisory parity evidence only.
    """
    if written_measure_index < 0:
        raise ValueError("written measure index must be non-negative")
    if occurrence < 1:
        raise ValueError("occurrence must be at least 1")
    for position in realized_measure_positions(sequence):
        if (
            position.written_measure_index == written_measure_index
            and position.occurrence == occurrence
        ):
            return position
    return None
