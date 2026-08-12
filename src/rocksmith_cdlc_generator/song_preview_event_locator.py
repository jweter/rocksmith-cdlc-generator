from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .musicxml_multi_import import ArrangementKind
from .song_preview import PreviewNoteEvent, SongPreviewSnapshot


class PreviewEventLocatorCandidate(BaseModel):
    """One immutable event candidate near a GUI timeline position."""

    selection_id: str
    event_index: int = Field(ge=0)
    distance_seconds: float = Field(ge=0)
    event: PreviewNoteEvent


class PreviewEventLocatorState(BaseModel):
    """Read-only candidate set for selecting an event from a timeline lane."""

    schema_version: int = 1
    instrument: ArrangementKind
    position_seconds: float = Field(ge=0)
    tolerance_seconds: float = Field(ge=0)
    match_kind: Literal["overlap", "nearby", "none"]
    candidates: list[PreviewEventLocatorCandidate] = Field(default_factory=list)


def _distance_to_event(note: PreviewNoteEvent, position_seconds: float) -> float:
    if note.start_seconds <= position_seconds < note.end_seconds:
        return 0.0
    if position_seconds < note.start_seconds:
        return note.start_seconds - position_seconds
    return position_seconds - note.end_seconds


def build_preview_event_locator(
    snapshot: SongPreviewSnapshot,
    instrument: ArrangementKind,
    position_seconds: float,
    *,
    tolerance_seconds: float = 0.08,
) -> PreviewEventLocatorState:
    """Return deterministic event candidates near a clicked timeline timestamp.

    Events whose half-open duration contains the timestamp are returned first as an
    ``overlap`` set. If no event overlaps, all events whose nearest boundary is within
    the explicit tolerance are returned as ``nearby`` candidates, ordered by distance,
    onset, then stable event index. Ambiguity is preserved as multiple candidates rather
    than silently choosing a musical event on the user's behalf.
    """

    if position_seconds < 0:
        raise ValueError("Preview locator position must be non-negative")
    if tolerance_seconds < 0:
        raise ValueError("Preview locator tolerance must be non-negative")

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

    overlapping = [
        note
        for note in arrangement.notes
        if note.start_seconds <= position_seconds < note.end_seconds
    ]
    if overlapping:
        ordered = sorted(overlapping, key=lambda note: (note.start_seconds, note.event_index))
        return PreviewEventLocatorState(
            instrument=instrument,
            position_seconds=position_seconds,
            tolerance_seconds=tolerance_seconds,
            match_kind="overlap",
            candidates=[
                PreviewEventLocatorCandidate(
                    selection_id=f"{instrument}:{note.event_index}",
                    event_index=note.event_index,
                    distance_seconds=0.0,
                    event=note.model_copy(deep=True),
                )
                for note in ordered
            ],
        )

    nearby = [
        (note, _distance_to_event(note, position_seconds))
        for note in arrangement.notes
    ]
    nearby = [
        (note, distance)
        for note, distance in nearby
        if distance <= tolerance_seconds
    ]
    nearby.sort(key=lambda item: (item[1], item[0].start_seconds, item[0].event_index))

    return PreviewEventLocatorState(
        instrument=instrument,
        position_seconds=position_seconds,
        tolerance_seconds=tolerance_seconds,
        match_kind="nearby" if nearby else "none",
        candidates=[
            PreviewEventLocatorCandidate(
                selection_id=f"{instrument}:{note.event_index}",
                event_index=note.event_index,
                distance_seconds=distance,
                event=note.model_copy(deep=True),
            )
            for note, distance in nearby
        ],
    )
