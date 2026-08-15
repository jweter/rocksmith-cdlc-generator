from __future__ import annotations

from pydantic import BaseModel, Field

from .musicxml_multi_import import ArrangementKind
from .song_preview import PreviewNoteEvent, SongPreviewSnapshot
from .song_preview_event_locator import build_preview_event_locator
from .song_preview_selection_handoff import build_preview_selection_handoff
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


class ArrangementEventSelectionState(BaseModel):
    """Read-only lane hit-test result that preserves musical ambiguity."""

    candidates: list[SelectedArrangementEvent] = Field(default_factory=list)
    requires_choice: bool = False


def _selected_event(*, arrangement, note: PreviewNoteEvent) -> SelectedArrangementEvent:
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


def locate_arrangement_events(
    snapshot: SongPreviewSnapshot,
    *,
    lane_index: int,
    time_seconds: float,
    tolerance_seconds: float = 0.05,
) -> ArrangementEventSelectionState:
    """Return every authoritative event candidate under/near one lane click.

    This delegates hit testing to the established preview locator/handoff contract.
    Overlapping notes (for example chord tones with identical timing) remain multiple
    candidates and therefore require an explicit human choice. No event index is chosen
    merely because it sorts first.
    """

    if lane_index < 0 or lane_index >= len(snapshot.arrangements):
        return ArrangementEventSelectionState()
    if time_seconds < 0:
        return ArrangementEventSelectionState()
    if tolerance_seconds < 0:
        raise ValueError("tolerance_seconds must be non-negative")

    arrangement = snapshot.arrangements[lane_index]
    locator = build_preview_event_locator(
        snapshot,
        arrangement.instrument,
        time_seconds,
        tolerance_seconds=tolerance_seconds,
    )
    handoff = build_preview_selection_handoff(snapshot, locator)

    return ArrangementEventSelectionState(
        candidates=[
            _selected_event(arrangement=arrangement, note=candidate.event)
            for candidate in locator.candidates
        ],
        requires_choice=handoff.requires_choice,
    )


def select_arrangement_event(
    snapshot: SongPreviewSnapshot,
    *,
    lane_index: int,
    time_seconds: float,
    tolerance_seconds: float = 0.05,
) -> SelectedArrangementEvent | None:
    """Return an event only when the lane click resolves unambiguously.

    Callers that need to present overlapping choices should use
    :func:`locate_arrangement_events`. Returning ``None`` for ambiguity is deliberate:
    it prevents a chord tone from receiving authority because of a stable-index tie.
    """

    state = locate_arrangement_events(
        snapshot,
        lane_index=lane_index,
        time_seconds=time_seconds,
        tolerance_seconds=tolerance_seconds,
    )
    if state.requires_choice or len(state.candidates) != 1:
        return None
    return state.candidates[0]
