from __future__ import annotations

from pydantic import BaseModel, Field

from .song_preview import SongPreviewSnapshot
from .song_preview_event_inspector import (
    PreviewEventSelectionState,
    build_preview_event_selection,
)
from .song_preview_event_locator import PreviewEventLocatorState


class PreviewSelectionHandoff(BaseModel):
    """Read-only bridge from timeline locator candidates to event inspection."""

    schema_version: int = 1
    candidate_selection_ids: list[str] = Field(default_factory=list)
    requires_choice: bool = False
    selected: PreviewEventSelectionState | None = None


def build_preview_selection_handoff(
    snapshot: SongPreviewSnapshot,
    locator: PreviewEventLocatorState,
    *,
    selection_id: str | None = None,
) -> PreviewSelectionHandoff:
    """Resolve locator candidates only when selection is unambiguous or explicit.

    A single candidate may be resolved automatically. Multiple candidates require an
    explicit ``selection_id`` supplied by the caller, preserving overlapping/chord-like
    ambiguity as a human-visible choice instead of guessing. Locator provenance must
    match the trusted snapshot before any event index is resolved, preventing stale
    locator state from selecting a similarly numbered event in a different song.
    """

    if (
        locator.source_filename != snapshot.source_filename
        or locator.source_sha256 != snapshot.source_sha256
    ):
        raise ValueError("Preview locator provenance does not match the supplied snapshot")

    candidate_ids = [candidate.selection_id for candidate in locator.candidates]
    if len(set(candidate_ids)) != len(candidate_ids):
        raise ValueError("Preview locator contains duplicate candidate selection ids")

    expected_ids = [
        f"{locator.instrument}:{candidate.event_index}"
        for candidate in locator.candidates
    ]
    if candidate_ids != expected_ids:
        raise ValueError("Preview locator candidate identity does not match instrument/event index")

    if locator.match_kind == "none" and locator.candidates:
        raise ValueError("Preview locator marked none but contains candidates")
    if locator.match_kind != "none" and not locator.candidates:
        raise ValueError("Preview locator match kind requires at least one candidate")

    if not locator.candidates:
        if selection_id is not None:
            raise ValueError("Cannot select an event from an empty locator result")
        return PreviewSelectionHandoff()

    if selection_id is None:
        if len(locator.candidates) > 1:
            return PreviewSelectionHandoff(
                candidate_selection_ids=list(candidate_ids),
                requires_choice=True,
            )
        selection_id = candidate_ids[0]

    if selection_id not in candidate_ids:
        raise ValueError(f"Selection id is not a locator candidate: {selection_id}")

    candidate = next(
        candidate
        for candidate in locator.candidates
        if candidate.selection_id == selection_id
    )
    selected = build_preview_event_selection(
        snapshot,
        locator.instrument,
        candidate.event_index,
    )
    return PreviewSelectionHandoff(
        candidate_selection_ids=list(candidate_ids),
        requires_choice=False,
        selected=selected,
    )
