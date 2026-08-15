from __future__ import annotations

from pydantic import BaseModel, Field

from .musicxml_multi_import import ArrangementKind
from .song_preview import SongPreviewSnapshot
from .source_import import SourceTrustClass


class SelectedArrangementEvent(BaseModel):
    """Stable GUI selection projected from one authoritative preview event."""

    instrument: ArrangementKind
    part_index: int = Field(ge=0)
    part_name: str
    event_index: int = Field(ge=0)
    start_seconds: float = Field(ge=0)
    duration_seconds: float = Field(gt=0)
    midi: int = Field(ge=0, le=127)
    note_name: str | None = None
    string_index: int | None = Field(default=None, ge=0)
    fret: int | None = Field(default=None, ge=0)
    techniques: list[str] = Field(default_factory=list)
    import_confidence: float = Field(ge=0, le=1)
    trust_class: SourceTrustClass
    review_required: bool

    @property
    def end_seconds(self) -> float:
        return self.start_seconds + self.duration_seconds


def select_arrangement_event(
    snapshot: SongPreviewSnapshot,
    *,
    lane_index: int,
    time_seconds: float,
    tolerance_seconds: float = 0.05,
) -> SelectedArrangementEvent | None:
    """Return the best event under/near one arrangement-lane click.

    Selection is read-only and deterministic. The tolerance exists only to make very
    short notes clickable; it never changes source timing or event authority.
    """

    if lane_index < 0 or lane_index >= len(snapshot.arrangements):
        return None
    if time_seconds < 0:
        return None
    if tolerance_seconds < 0:
        raise ValueError("tolerance_seconds must be non-negative")

    arrangement = snapshot.arrangements[lane_index]
    candidates = []
    for note in arrangement.notes:
        start = note.start_seconds
        end = note.end_seconds
        if time_seconds < start - tolerance_seconds or time_seconds > end + tolerance_seconds:
            continue
        if time_seconds < start:
            edge_distance = start - time_seconds
        elif time_seconds > end:
            edge_distance = time_seconds - end
        else:
            edge_distance = 0.0
        midpoint_distance = abs(time_seconds - ((start + end) / 2.0))
        candidates.append((edge_distance, midpoint_distance, note.event_index, note))

    if not candidates:
        return None

    _, _, _, note = min(candidates, key=lambda item: (item[0], item[1], item[2]))
    return SelectedArrangementEvent(
        instrument=arrangement.instrument,
        part_index=arrangement.part_index,
        part_name=arrangement.part_name,
        event_index=note.event_index,
        start_seconds=note.start_seconds,
        duration_seconds=note.duration_seconds,
        midi=note.midi,
        note_name=note.note_name,
        string_index=note.string_index,
        fret=note.fret,
        techniques=list(note.techniques),
        import_confidence=note.import_confidence,
        trust_class=note.trust_class,
        review_required=note.review_required,
    )
