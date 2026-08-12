from __future__ import annotations

from math import isfinite

from pydantic import BaseModel, Field

from .musicxml_multi_import import ArrangementKind
from .song_preview import PreviewNoteEvent, SongPreviewSnapshot, build_preview_timeline_window


class PreviewRenderBeat(BaseModel):
    """One canonical beat positioned inside a normalized timeline viewport."""

    beat_index: int = Field(ge=0)
    time_seconds: float = Field(ge=0)
    x_fraction: float = Field(ge=0, le=1)


class PreviewRenderEvent(BaseModel):
    """One immutable arrangement event rectangle for timeline rendering."""

    selection_id: str
    event_index: int = Field(ge=0)
    clipped_start_seconds: float = Field(ge=0)
    clipped_end_seconds: float = Field(ge=0)
    x_start_fraction: float = Field(ge=0, le=1)
    x_end_fraction: float = Field(ge=0, le=1)
    event: PreviewNoteEvent


class PreviewRenderLane(BaseModel):
    instrument: ArrangementKind
    part_name: str
    tuning_midi: list[int] | None = None
    events: list[PreviewRenderEvent] = Field(default_factory=list)


class PreviewTimelineRenderGeometry(BaseModel):
    """Framework-neutral 0..1 geometry for a read-only Song Preview viewport."""

    schema_version: int = 1
    source_filename: str
    source_sha256: str
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)
    duration_seconds: float = Field(gt=0)
    beats: list[PreviewRenderBeat] = Field(default_factory=list)
    lanes: list[PreviewRenderLane] = Field(default_factory=list)


def _fraction(time_seconds: float, start_seconds: float, duration_seconds: float) -> float:
    return (time_seconds - start_seconds) / duration_seconds


def build_preview_timeline_render_geometry(
    snapshot: SongPreviewSnapshot,
    start_seconds: float,
    end_seconds: float,
) -> PreviewTimelineRenderGeometry:
    """Convert trusted preview timing into framework-neutral normalized render geometry.

    The function builds its viewport directly from the trusted snapshot so geometry is
    provenance-bound to one source. Notes crossing a viewport edge are clipped only in
    the render projection; their copied authoritative timing remains unchanged in
    ``event``. Event rectangles follow half-open viewport semantics so an event that
    starts exactly at the viewport end is not emitted as a zero-width rectangle.
    No timing correction or source mutation occurs here.
    """

    if not isfinite(start_seconds) or not isfinite(end_seconds):
        raise ValueError("Preview render viewport endpoints must be finite")
    if start_seconds < 0:
        raise ValueError("Preview render start must be non-negative")
    if end_seconds <= start_seconds:
        raise ValueError("Preview render end must be greater than start")

    beat_times = snapshot.beat_times_seconds
    if any(right <= left for left, right in zip(beat_times, beat_times[1:])):
        raise ValueError("Preview render requires a strictly increasing canonical beat grid")

    roles = [arrangement.instrument for arrangement in snapshot.arrangements]
    if len(set(roles)) != len(roles):
        raise ValueError("Preview render snapshot contains duplicate arrangement roles")
    for arrangement in snapshot.arrangements:
        event_ids = [note.event_index for note in arrangement.notes]
        if len(set(event_ids)) != len(event_ids):
            raise ValueError(
                f"Preview render arrangement contains duplicate event indices: {arrangement.instrument}"
            )

    window = build_preview_timeline_window(snapshot, start_seconds, end_seconds)
    duration = end_seconds - start_seconds

    beat_index_by_time = {time_seconds: index for index, time_seconds in enumerate(beat_times)}
    beats = [
        PreviewRenderBeat(
            beat_index=beat_index_by_time[time_seconds],
            time_seconds=time_seconds,
            x_fraction=_fraction(time_seconds, start_seconds, duration),
        )
        for time_seconds in window.beat_times_seconds
    ]

    lanes: list[PreviewRenderLane] = []
    for lane in window.lanes:
        events: list[PreviewRenderEvent] = []
        for note in sorted(lane.notes, key=lambda item: (item.start_seconds, item.event_index)):
            clipped_start = max(note.start_seconds, start_seconds)
            clipped_end = min(note.end_seconds, end_seconds)
            if clipped_end <= clipped_start:
                continue
            events.append(
                PreviewRenderEvent(
                    selection_id=f"{lane.instrument}:{note.event_index}",
                    event_index=note.event_index,
                    clipped_start_seconds=clipped_start,
                    clipped_end_seconds=clipped_end,
                    x_start_fraction=_fraction(clipped_start, start_seconds, duration),
                    x_end_fraction=_fraction(clipped_end, start_seconds, duration),
                    event=note.model_copy(deep=True),
                )
            )
        lanes.append(
            PreviewRenderLane(
                instrument=lane.instrument,
                part_name=lane.part_name,
                tuning_midi=list(lane.tuning_midi) if lane.tuning_midi is not None else None,
                events=events,
            )
        )

    return PreviewTimelineRenderGeometry(
        source_filename=snapshot.source_filename,
        source_sha256=snapshot.source_sha256,
        start_seconds=start_seconds,
        end_seconds=end_seconds,
        duration_seconds=duration,
        beats=beats,
        lanes=lanes,
    )
