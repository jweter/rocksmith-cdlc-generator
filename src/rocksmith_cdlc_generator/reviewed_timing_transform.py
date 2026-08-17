from __future__ import annotations

from bisect import bisect_right

from .reviewed_arrangement_timing import ReviewedArrangementTiming


def map_reviewed_source_time(
    timing: ReviewedArrangementTiming,
    source_time_seconds: float,
) -> float:
    """Map one symbolic source timestamp through promoted reviewed song timing.

    The transform is piecewise linear between neighboring promoted score beats. Times
    before the first or after the last score beat use the nearest edge segment, matching
    the existing alignment transform without inventing additional anchors.
    """

    source_time = float(source_time_seconds)
    if source_time < 0:
        raise ValueError("source time must be non-negative")
    if len(timing.points) < 2:
        raise ValueError("reviewed arrangement timing needs at least two score beats")

    points = timing.points
    if source_time <= points[0].source_time_seconds:
        first, second = points[0], points[1]
    elif source_time >= points[-1].source_time_seconds:
        first, second = points[-2], points[-1]
    else:
        source_times = [point.source_time_seconds for point in points]
        right = bisect_right(source_times, source_time)
        first, second = points[right - 1], points[right]

    source_span = second.source_time_seconds - first.source_time_seconds
    if source_span <= 0:
        raise ValueError("reviewed arrangement source beats must be strictly increasing")
    reviewed_span = second.reviewed_time_seconds - first.reviewed_time_seconds
    if reviewed_span <= 0:
        raise ValueError("reviewed arrangement recording beats must be strictly increasing")

    fraction = (source_time - first.source_time_seconds) / source_span
    return first.reviewed_time_seconds + fraction * reviewed_span


def map_reviewed_source_interval(
    timing: ReviewedArrangementTiming,
    source_start_seconds: float,
    source_duration_seconds: float,
) -> tuple[float, float]:
    """Map a source note/event interval to reviewed recording start and duration.

    Returning a duration derived from mapping both endpoints preserves local tempo changes
    introduced by accepted bounded refits instead of applying a single global scale.
    """

    source_start = float(source_start_seconds)
    source_duration = float(source_duration_seconds)
    if source_start < 0:
        raise ValueError("source start must be non-negative")
    if source_duration <= 0:
        raise ValueError("source duration must be positive")

    reviewed_start = map_reviewed_source_time(timing, source_start)
    reviewed_end = map_reviewed_source_time(timing, source_start + source_duration)
    reviewed_duration = reviewed_end - reviewed_start
    if reviewed_duration <= 0:
        raise ValueError("reviewed timing collapsed or reversed the source interval")
    return reviewed_start, reviewed_duration
