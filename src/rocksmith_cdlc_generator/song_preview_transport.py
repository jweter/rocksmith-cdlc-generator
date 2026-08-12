from __future__ import annotations

from pydantic import BaseModel, Field

from .song_preview_loop import PreviewLoopRange, wrap_preview_playhead


class PreviewTransportState(BaseModel):
    """Deterministic read-only transport projection for the future Song Workspace."""

    schema_version: int = 1
    requested_position_seconds: float = Field(ge=0)
    effective_position_seconds: float = Field(ge=0)
    loop_range: PreviewLoopRange | None = None
    loop_enabled: bool = False


def build_preview_transport_state(
    position_seconds: float,
    *,
    loop_range: PreviewLoopRange | None = None,
    loop_enabled: bool = False,
) -> PreviewTransportState:
    """Resolve a requested transport position without touching audio or chart state.

    Loop wrapping is applied only when an explicit loop exists and is enabled. The
    requested position is retained so a GUI/audio backend can distinguish user intent
    from the effective position used by synchronized preview consumers.
    """

    if position_seconds < 0:
        raise ValueError("Preview transport position must be non-negative")
    if loop_enabled and loop_range is None:
        raise ValueError("Loop playback requires an explicit loop range")

    effective_position = (
        wrap_preview_playhead(loop_range, position_seconds)
        if loop_enabled and loop_range is not None
        else position_seconds
    )

    return PreviewTransportState(
        requested_position_seconds=position_seconds,
        effective_position_seconds=effective_position,
        loop_range=loop_range.model_copy(deep=True) if loop_range is not None else None,
        loop_enabled=loop_enabled,
    )
