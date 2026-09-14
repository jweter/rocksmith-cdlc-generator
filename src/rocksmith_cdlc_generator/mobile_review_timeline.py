"""Privacy-safe timeline landmarks for mobile Product Reality review.

This module consumes only already-derived Product Reality observations. It never
reads audio, score, DLC, Rocksmith installation data, or private source paths.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from .private_product_reality import PrivateProductRealityEvidence


@dataclass(frozen=True, slots=True)
class MobileTimelineLandmark:
    arrangement: str
    kind: Literal["first_event", "checkpoint"]
    seconds: float
    label: str


def _validated_seconds(value: object, *, field: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{field} must be numeric")
    seconds = float(value)
    if not isfinite(seconds) or seconds < 0.0:
        raise ValueError(f"{field} must be finite and non-negative")
    return seconds


def build_mobile_timeline_landmarks(
    evidence: "PrivateProductRealityEvidence",
) -> tuple[MobileTimelineLandmark, ...]:
    """Project sanitized timing evidence onto one deterministic shared timeline.

    First-event and checkpoint observations are expressed in the same recording-time
    coordinate system already used by Product Reality evidence. Sorting by timestamp and
    stable textual tie-breakers makes the result byte-stable for rendering/tests while
    preserving Bass/Lead/Rhythm as distinct first-class arrangements.
    """

    landmarks: list[MobileTimelineLandmark] = []

    for observation in evidence.role_observations:
        arrangement = observation.role.value
        landmarks.append(
            MobileTimelineLandmark(
                arrangement=arrangement,
                kind="first_event",
                seconds=_validated_seconds(
                    observation.first_playable_seconds,
                    field=f"{arrangement} first_playable_seconds",
                ),
                label="First playable",
            )
        )

    for checkpoint in evidence.checkpoint_observations:
        arrangement = checkpoint.role.value
        checkpoint_id = str(checkpoint.checkpoint_id).strip()
        if not checkpoint_id:
            raise ValueError("checkpoint_id must be non-empty")
        landmarks.append(
            MobileTimelineLandmark(
                arrangement=arrangement,
                kind="checkpoint",
                seconds=_validated_seconds(
                    checkpoint.observed_audio_seconds,
                    field=f"{arrangement} checkpoint observed_audio_seconds",
                ),
                label=f"Checkpoint {checkpoint_id}",
            )
        )

    return tuple(
        sorted(
            landmarks,
            key=lambda item: (item.seconds, item.arrangement, item.kind, item.label),
        )
    )
