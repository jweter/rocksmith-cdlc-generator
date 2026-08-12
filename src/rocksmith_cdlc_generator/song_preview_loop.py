from __future__ import annotations

from pydantic import BaseModel, Field

from .song_preview import SongPreviewSnapshot


class PreviewLoopRange(BaseModel):
    """Read-only transport selection that never mutates chart or timing data."""

    schema_version: int = 1
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)
    duration_seconds: float = Field(gt=0)
    beat_indices: list[int] = Field(default_factory=list)
    beat_times_seconds: list[float] = Field(default_factory=list)


def build_preview_loop_range(
    snapshot: SongPreviewSnapshot,
    start_seconds: float,
    end_seconds: float,
) -> PreviewLoopRange:
    """Build a deterministic loop selection over the trusted preview timebase.

    The range is independent from authoritative timing artifacts: it records only user-facing
    transport bounds plus the canonical beats that fall inside them. Beat indices always refer
    to the full snapshot so viewport/transport consumers do not silently renumber timing data.
    """

    if start_seconds < 0:
        raise ValueError("Loop start must be non-negative")
    if end_seconds <= start_seconds:
        raise ValueError("Loop end must be greater than loop start")

    beat_indices: list[int] = []
    beat_times: list[float] = []
    for index, beat in enumerate(snapshot.beat_times_seconds):
        if start_seconds <= beat < end_seconds:
            beat_indices.append(index)
            beat_times.append(beat)

    return PreviewLoopRange(
        start_seconds=start_seconds,
        end_seconds=end_seconds,
        duration_seconds=end_seconds - start_seconds,
        beat_indices=beat_indices,
        beat_times_seconds=beat_times,
    )


def wrap_preview_playhead(loop_range: PreviewLoopRange, position_seconds: float) -> float:
    """Map a transport position into the loop using deterministic modulo wrapping.

    Positions before the loop start are left unchanged so a future transport can support
    pre-roll. Positions at or beyond the loop end wrap into the selected interval.
    """

    if position_seconds < 0:
        raise ValueError("Preview playhead position must be non-negative")
    if position_seconds < loop_range.start_seconds:
        return position_seconds
    if position_seconds < loop_range.end_seconds:
        return position_seconds

    offset = (position_seconds - loop_range.start_seconds) % loop_range.duration_seconds
    return loop_range.start_seconds + offset
