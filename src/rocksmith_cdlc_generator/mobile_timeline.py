"""Deterministic, privacy-safe timeline landmarks for mobile Product Reality review.

This module consumes only already-sanitized Product Reality evidence. It never reads
commercial/private audio, score bytes, workspaces, packages, or Rocksmith installs.
"""

from __future__ import annotations

from math import isfinite
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .private_product_reality import PrivateProductRealityEvidence


def build_mobile_timeline_landmarks(evidence: "PrivateProductRealityEvidence") -> list[dict[str, Any]]:
    """Return deterministic first-event/checkpoint landmarks for mobile review.

    Landmarks are ordered by timestamp, then arrangement, kind, and stable identifier so
    coincident evidence produces reproducible output. Invalid/non-finite timestamps fail closed.
    """
    landmarks: list[dict[str, Any]] = []

    for observation in evidence.role_observations:
        timestamp = float(observation.first_playable_seconds)
        _validate_timestamp(timestamp, f"{observation.role.value} first playable")
        landmarks.append(
            {
                "kind": "first_playable",
                "arrangement": observation.role.value,
                "id": f"{observation.role.value}:first_playable",
                "seconds": timestamp,
            }
        )

    for checkpoint in evidence.checkpoint_observations:
        timestamp = float(checkpoint.observed_audio_seconds)
        expected_timestamp = float(checkpoint.expected_audio_seconds)
        _validate_timestamp(timestamp, f"checkpoint {checkpoint.checkpoint_id}")
        _validate_timestamp(expected_timestamp, f"checkpoint {checkpoint.checkpoint_id} expected")
        landmarks.append(
            {
                "kind": "checkpoint",
                "arrangement": checkpoint.role.value,
                "id": checkpoint.checkpoint_id,
                "seconds": timestamp,
                "expected_seconds": expected_timestamp,
            }
        )

    landmarks.sort(
        key=lambda item: (
            item["seconds"],
            item["arrangement"],
            item["kind"],
            item["id"],
        )
    )
    return landmarks


def _validate_timestamp(value: float, label: str) -> None:
    if not isfinite(value) or value < 0.0:
        raise ValueError(f"invalid mobile timeline timestamp for {label}: {value!r}")
