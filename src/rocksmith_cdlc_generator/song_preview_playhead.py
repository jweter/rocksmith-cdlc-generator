from __future__ import annotations

from pydantic import BaseModel, Field

from .musicxml_multi_import import ArrangementKind
from .song_preview import PreviewNoteEvent, SongPreviewSnapshot


class PreviewPlayheadLane(BaseModel):
    """Read-only arrangement state at one playhead position."""

    instrument: ArrangementKind
    part_name: str
    tuning_midi: list[int] | None = None
    active_notes: list[PreviewNoteEvent] = Field(default_factory=list)
    next_note: PreviewNoteEvent | None = None


class PreviewPlayheadState(BaseModel):
    """GUI-friendly synchronized state derived from a trusted preview snapshot."""

    schema_version: int = 1
    position_seconds: float = Field(ge=0)
    previous_beat_seconds: float | None = Field(default=None, ge=0)
    next_beat_seconds: float | None = Field(default=None, ge=0)
    lanes: list[PreviewPlayheadLane] = Field(default_factory=list)


def build_preview_playhead_state(
    snapshot: SongPreviewSnapshot,
    position_seconds: float,
) -> PreviewPlayheadState:
    """Project active/upcoming arrangement events at one immutable playhead position.

    Active-note intervals are half-open: ``start <= position < end``. This prevents a
    note from remaining active at the exact instant its duration ends. Returned notes
    and tunings are copied so GUI-side state cannot mutate the trusted snapshot.
    """

    if position_seconds < 0:
        raise ValueError("Preview playhead position must be non-negative")

    previous_beat = next(
        (
            beat
            for beat in reversed(snapshot.beat_times_seconds)
            if beat <= position_seconds
        ),
        None,
    )
    next_beat = next(
        (beat for beat in snapshot.beat_times_seconds if beat > position_seconds),
        None,
    )

    lanes: list[PreviewPlayheadLane] = []
    for arrangement in snapshot.arrangements:
        active_notes = [
            note.model_copy(deep=True)
            for note in arrangement.notes
            if note.start_seconds <= position_seconds < note.end_seconds
        ]
        next_note = next(
            (
                note.model_copy(deep=True)
                for note in arrangement.notes
                if note.start_seconds > position_seconds
            ),
            None,
        )
        lanes.append(
            PreviewPlayheadLane(
                instrument=arrangement.instrument,
                part_name=arrangement.part_name,
                tuning_midi=(
                    list(arrangement.tuning_midi)
                    if arrangement.tuning_midi is not None
                    else None
                ),
                active_notes=active_notes,
                next_note=next_note,
            )
        )

    return PreviewPlayheadState(
        position_seconds=position_seconds,
        previous_beat_seconds=previous_beat,
        next_beat_seconds=next_beat,
        lanes=lanes,
    )
