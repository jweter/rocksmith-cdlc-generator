from __future__ import annotations

from pydantic import BaseModel, Field

from .song_preview import SongPreviewSnapshot


class PreviewClickEvent(BaseModel):
    """One canonical beat event for variable-tempo preview playback."""

    beat_index: int = Field(ge=0)
    time_seconds: float = Field(ge=0)
    interval_from_previous_seconds: float | None = Field(default=None, gt=0)
    interval_to_next_seconds: float | None = Field(default=None, gt=0)
    local_bpm: float | None = Field(default=None, gt=0)


class PreviewClickSchedule(BaseModel):
    """Read-only click schedule derived from the trusted canonical beat grid."""

    schema_version: int = 1
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)
    events: list[PreviewClickEvent] = Field(default_factory=list)


def build_preview_click_schedule(
    snapshot: SongPreviewSnapshot,
    start_seconds: float = 0.0,
    end_seconds: float | None = None,
) -> PreviewClickSchedule:
    """Return canonical beat timestamps for a variable-tempo preview metronome.

    The schedule never synthesizes, quantizes, or moves beats. Local BPM is calculated
    from the interval to the following canonical beat where available. Beat indices stay
    anchored to the complete snapshot even when a viewport/range is requested.
    """

    if start_seconds < 0:
        raise ValueError("Click schedule start must be non-negative")

    beats = list(snapshot.beat_times_seconds)
    if any(right <= left for left, right in zip(beats, beats[1:])):
        raise ValueError("Canonical preview beat grid must be strictly increasing")

    resolved_end = end_seconds
    if resolved_end is None:
        resolved_end = max(start_seconds, beats[-1]) if beats else start_seconds
    if resolved_end < start_seconds:
        raise ValueError("Click schedule end must be greater than or equal to start")

    events: list[PreviewClickEvent] = []
    for index, beat in enumerate(beats):
        if not start_seconds <= beat <= resolved_end:
            continue

        previous_interval = beat - beats[index - 1] if index > 0 else None
        next_interval = beats[index + 1] - beat if index + 1 < len(beats) else None
        events.append(
            PreviewClickEvent(
                beat_index=index,
                time_seconds=beat,
                interval_from_previous_seconds=previous_interval,
                interval_to_next_seconds=next_interval,
                local_bpm=(60.0 / next_interval if next_interval is not None else None),
            )
        )

    return PreviewClickSchedule(
        start_seconds=start_seconds,
        end_seconds=resolved_end,
        events=events,
    )
