from __future__ import annotations

from pydantic import BaseModel, Field

from .musicxml_multi_import import ArrangementKind
from .song_preview import SourceTrustClass
from .song_preview_playhead import PreviewPlayheadState


class PreviewFretboardMarker(BaseModel):
    """One trusted physical string/fret position for fretboard rendering."""

    event_index: int = Field(ge=0)
    string_index: int = Field(ge=0)
    fret: int = Field(ge=0)
    midi: int = Field(ge=0, le=127)
    note_name: str | None = None
    import_confidence: float = Field(ge=0, le=1)
    trust_class: SourceTrustClass
    review_required: bool
    is_active: bool


class PreviewFretboardLane(BaseModel):
    instrument: ArrangementKind
    part_name: str
    tuning_midi: list[int]
    active_markers: list[PreviewFretboardMarker] = Field(default_factory=list)
    upcoming_marker: PreviewFretboardMarker | None = None
    unmapped_active_event_indices: list[int] = Field(default_factory=list)
    unmapped_upcoming_event_index: int | None = Field(default=None, ge=0)


class PreviewFretboardState(BaseModel):
    """Read-only physical-position projection at one playhead position."""

    schema_version: int = 1
    position_seconds: float = Field(ge=0)
    lanes: list[PreviewFretboardLane] = Field(default_factory=list)


def _marker(note, *, is_active: bool) -> PreviewFretboardMarker | None:
    if note.string_index is None or note.fret is None:
        return None
    return PreviewFretboardMarker(
        event_index=note.event_index,
        string_index=note.string_index,
        fret=note.fret,
        midi=note.midi,
        note_name=note.note_name,
        import_confidence=note.import_confidence,
        trust_class=note.trust_class,
        review_required=note.review_required,
        is_active=is_active,
    )


def build_preview_fretboard_state(playhead: PreviewPlayheadState) -> PreviewFretboardState:
    """Project trusted string/fret data for a virtual fretboard without inventing mapping.

    Events without explicit physical positions remain visible through unmapped event IDs.
    This layer never infers alternate positions or writes corrections.
    """

    lanes: list[PreviewFretboardLane] = []
    for lane in playhead.lanes:
        if lane.tuning_midi is None:
            continue

        active_markers: list[PreviewFretboardMarker] = []
        unmapped_active: list[int] = []
        for note in lane.active_notes:
            marker = _marker(note, is_active=True)
            if marker is None:
                unmapped_active.append(note.event_index)
            else:
                active_markers.append(marker)

        upcoming_marker = None
        unmapped_upcoming = None
        if lane.next_note is not None:
            upcoming_marker = _marker(lane.next_note, is_active=False)
            if upcoming_marker is None:
                unmapped_upcoming = lane.next_note.event_index

        lanes.append(
            PreviewFretboardLane(
                instrument=lane.instrument,
                part_name=lane.part_name,
                tuning_midi=list(lane.tuning_midi),
                active_markers=active_markers,
                upcoming_marker=upcoming_marker,
                unmapped_active_event_indices=unmapped_active,
                unmapped_upcoming_event_index=unmapped_upcoming,
            )
        )

    return PreviewFretboardState(position_seconds=playhead.position_seconds, lanes=lanes)
