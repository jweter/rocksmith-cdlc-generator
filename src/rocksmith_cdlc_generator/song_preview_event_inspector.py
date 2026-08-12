from __future__ import annotations

from pydantic import BaseModel, Field

from .musicxml_multi_import import ArrangementKind
from .song_preview import PreviewNoteEvent, SongPreviewSnapshot


class PreviewEventSelectionState(BaseModel):
    """Read-only detail state for one selected arrangement event."""

    schema_version: int = 1
    selection_id: str
    source_filename: str
    source_sha256: str
    instrument: ArrangementKind
    part_index: int = Field(ge=0)
    part_id: str
    part_name: str
    tuning_midi: list[int] | None = None
    selected: PreviewNoteEvent
    previous_event: PreviewNoteEvent | None = None
    next_event: PreviewNoteEvent | None = None
    review_id: str | None = None


def build_preview_event_selection(
    snapshot: SongPreviewSnapshot,
    instrument: ArrangementKind,
    event_index: int,
) -> PreviewEventSelectionState:
    """Return immutable GUI detail state for one stable arrangement event identifier.

    The caller selects by arrangement role plus the full-arrangement ``event_index``.
    Neighboring events are derived in chronological order with ``event_index`` as the
    deterministic tie-breaker. Returned notes and tunings are copied so inspector/UI
    state cannot mutate the trusted preview snapshot.
    """

    if event_index < 0:
        raise ValueError("Preview event index must be non-negative")

    arrangements = [
        arrangement
        for arrangement in snapshot.arrangements
        if arrangement.instrument == instrument
    ]
    if not arrangements:
        raise ValueError(f"Preview arrangement not found: {instrument}")
    if len(arrangements) != 1:
        raise ValueError(f"Preview snapshot contains duplicate arrangement role: {instrument}")

    arrangement = arrangements[0]
    event_ids = [note.event_index for note in arrangement.notes]
    if len(set(event_ids)) != len(event_ids):
        raise ValueError(f"Preview arrangement contains duplicate event indices: {instrument}")

    ordered = sorted(
        arrangement.notes,
        key=lambda note: (note.start_seconds, note.event_index),
    )
    selected_position = next(
        (
            position
            for position, note in enumerate(ordered)
            if note.event_index == event_index
        ),
        None,
    )
    if selected_position is None:
        raise ValueError(f"Preview event not found: {instrument}:{event_index}")

    selected = ordered[selected_position]
    previous_event = ordered[selected_position - 1] if selected_position > 0 else None
    next_event = (
        ordered[selected_position + 1]
        if selected_position + 1 < len(ordered)
        else None
    )
    selection_id = f"{instrument}:{event_index}"

    return PreviewEventSelectionState(
        selection_id=selection_id,
        source_filename=snapshot.source_filename,
        source_sha256=snapshot.source_sha256,
        instrument=arrangement.instrument,
        part_index=arrangement.part_index,
        part_id=arrangement.part_id,
        part_name=arrangement.part_name,
        tuning_midi=(
            list(arrangement.tuning_midi)
            if arrangement.tuning_midi is not None
            else None
        ),
        selected=selected.model_copy(deep=True),
        previous_event=(
            previous_event.model_copy(deep=True)
            if previous_event is not None
            else None
        ),
        next_event=(
            next_event.model_copy(deep=True)
            if next_event is not None
            else None
        ),
        review_id=selection_id if selected.review_required else None,
    )
