from __future__ import annotations

import math

from pydantic import BaseModel, Field

from .musicxml_multi_import import ArrangementKind
from .song_preview import SongPreviewSnapshot
from .song_preview_event_locator import (
    PreviewEventLocatorState,
    build_preview_event_locator,
)
from .song_preview_render import PreviewTimelineRenderGeometry


class PreviewTimelineInteractionState(BaseModel):
    """Read-only bridge from normalized render coordinates to trusted song time."""

    schema_version: int = 1
    source_filename: str
    source_sha256: str
    instrument: ArrangementKind
    x_fraction: float = Field(ge=0, le=1)
    position_seconds: float = Field(ge=0)
    tolerance_seconds: float = Field(ge=0)
    locator: PreviewEventLocatorState


def build_preview_timeline_interaction(
    snapshot: SongPreviewSnapshot,
    geometry: PreviewTimelineRenderGeometry,
    instrument: ArrangementKind,
    x_fraction: float,
    *,
    tolerance_seconds: float,
) -> PreviewTimelineInteractionState:
    """Translate one normalized lane interaction into an absolute timestamp and locator.

    The render geometry must belong to the supplied trusted snapshot. The caller must
    provide an explicit event-selection tolerance; no click policy is invented here.
    Geometry is treated as an untrusted GUI-facing projection and its viewport duration
    is revalidated before the timestamp is derived. The resulting locator is rebuilt
    from the trusted snapshot rather than from rendered event rectangles.
    """

    if (
        geometry.source_filename != snapshot.source_filename
        or geometry.source_sha256 != snapshot.source_sha256
    ):
        raise ValueError("Preview render geometry provenance does not match the supplied snapshot")

    if not math.isfinite(x_fraction):
        raise ValueError("Preview interaction x fraction must be finite")
    if not 0 <= x_fraction <= 1:
        raise ValueError("Preview interaction x fraction must be between 0 and 1")
    if not math.isfinite(tolerance_seconds):
        raise ValueError("Preview interaction tolerance must be finite")
    if tolerance_seconds < 0:
        raise ValueError("Preview interaction tolerance must be non-negative")

    if not math.isfinite(geometry.start_seconds) or not math.isfinite(geometry.end_seconds):
        raise ValueError("Preview render geometry viewport endpoints must be finite")
    expected_duration = geometry.end_seconds - geometry.start_seconds
    if not math.isfinite(expected_duration) or expected_duration <= 0:
        raise ValueError("Preview render geometry duration must be finite and positive")
    if not math.isfinite(geometry.duration_seconds) or not math.isclose(
        geometry.duration_seconds,
        expected_duration,
        rel_tol=1e-12,
        abs_tol=1e-12,
    ):
        raise ValueError("Preview render geometry duration is inconsistent with its viewport")

    position_seconds = geometry.start_seconds + (x_fraction * expected_duration)
    if not math.isfinite(position_seconds):
        raise ValueError("Preview interaction produced a non-finite song position")

    locator = build_preview_event_locator(
        snapshot,
        instrument,
        position_seconds,
        tolerance_seconds=tolerance_seconds,
    )
    return PreviewTimelineInteractionState(
        source_filename=snapshot.source_filename,
        source_sha256=snapshot.source_sha256,
        instrument=instrument,
        x_fraction=x_fraction,
        position_seconds=position_seconds,
        tolerance_seconds=tolerance_seconds,
        locator=locator,
    )
