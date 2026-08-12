from __future__ import annotations

from pydantic import BaseModel, Field

from .song_preview import (
    PreviewTimelineWindow,
    SongPreviewSnapshot,
    build_preview_review_queue,
    build_preview_timeline_window,
)
from .song_preview_context import PreviewMusicalContext, build_preview_musical_context
from .song_preview_fretboard import PreviewFretboardState, build_preview_fretboard_state
from .song_preview_playhead import PreviewPlayheadState, build_preview_playhead_state
from .song_preview_review_nav import (
    PreviewReviewNavigationState,
    build_review_navigation_from_position,
)


class PreviewWorkspaceState(BaseModel):
    """One synchronized, read-only Song Workspace view-model snapshot."""

    schema_version: int = 1
    viewport: PreviewTimelineWindow
    playhead: PreviewPlayheadState
    musical_context: PreviewMusicalContext
    fretboard: PreviewFretboardState
    review_required_total: int = Field(ge=0)
    review_navigation: PreviewReviewNavigationState | None = None


def build_preview_workspace_state(
    snapshot: SongPreviewSnapshot,
    *,
    viewport_start_seconds: float,
    viewport_end_seconds: float,
    playhead_seconds: float,
) -> PreviewWorkspaceState:
    """Compose existing trusted preview consumers into one GUI-facing state object.

    The function deliberately performs no editing and writes no artifacts. Each nested
    consumer keeps its existing validation and copy boundaries, giving a future Qt view
    one deterministic state contract instead of requiring it to coordinate raw source
    models directly.
    """

    viewport = build_preview_timeline_window(
        snapshot,
        viewport_start_seconds,
        viewport_end_seconds,
    )
    playhead = build_preview_playhead_state(snapshot, playhead_seconds)
    musical_context = build_preview_musical_context(snapshot, playhead_seconds)
    fretboard = build_preview_fretboard_state(playhead)

    review_queue = build_preview_review_queue(snapshot)
    review_navigation = (
        build_review_navigation_from_position(review_queue, playhead_seconds)
        if review_queue.items
        else None
    )

    return PreviewWorkspaceState(
        viewport=viewport,
        playhead=playhead,
        musical_context=musical_context,
        fretboard=fretboard,
        review_required_total=len(review_queue.items),
        review_navigation=review_navigation,
    )
