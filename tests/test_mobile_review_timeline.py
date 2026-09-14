from __future__ import annotations

from types import SimpleNamespace

import pytest

from rocksmith_cdlc_generator.mobile_review_timeline import build_mobile_timeline_landmarks
from rocksmith_cdlc_generator.score_source import ArrangementRole


def _role(role: ArrangementRole, first_playable_seconds: float) -> SimpleNamespace:
    return SimpleNamespace(role=role, first_playable_seconds=first_playable_seconds)


def _checkpoint(
    role: ArrangementRole,
    checkpoint_id: str,
    observed_audio_seconds: float,
) -> SimpleNamespace:
    return SimpleNamespace(
        role=role,
        checkpoint_id=checkpoint_id,
        observed_audio_seconds=observed_audio_seconds,
    )


def test_timeline_landmarks_are_shared_and_deterministically_ordered() -> None:
    evidence = SimpleNamespace(
        role_observations=[
            _role(ArrangementRole.RHYTHM, 12.0),
            _role(ArrangementRole.BASS, 9.0),
            _role(ArrangementRole.LEAD, 9.0),
        ],
        checkpoint_observations=[
            _checkpoint(ArrangementRole.BASS, "later", 77.8),
            _checkpoint(ArrangementRole.LEAD, "chorus", 42.0),
        ],
    )

    landmarks = build_mobile_timeline_landmarks(evidence)

    assert [(item.seconds, item.arrangement, item.kind, item.label) for item in landmarks] == [
        (9.0, "bass", "first_event", "First playable"),
        (9.0, "lead", "first_event", "First playable"),
        (12.0, "rhythm", "first_event", "First playable"),
        (42.0, "lead", "checkpoint", "Checkpoint chorus"),
        (77.8, "bass", "checkpoint", "Checkpoint later"),
    ]


def test_timeline_landmarks_reject_invalid_timestamps() -> None:
    evidence = SimpleNamespace(
        role_observations=[_role(ArrangementRole.BASS, float("nan"))],
        checkpoint_observations=[],
    )

    with pytest.raises(ValueError, match="finite and non-negative"):
        build_mobile_timeline_landmarks(evidence)


def test_timeline_landmarks_reject_blank_checkpoint_ids() -> None:
    evidence = SimpleNamespace(
        role_observations=[],
        checkpoint_observations=[_checkpoint(ArrangementRole.LEAD, "   ", 12.0)],
    )

    with pytest.raises(ValueError, match="checkpoint_id must be non-empty"):
        build_mobile_timeline_landmarks(evidence)


def test_timeline_landmarks_do_not_expose_expected_timing_or_source_material() -> None:
    checkpoint = _checkpoint(ArrangementRole.BASS, "anchor", 30.0)
    checkpoint.expected_audio_seconds = 29.5
    checkpoint.private_source_path = r"C:\private\song.gp5"
    evidence = SimpleNamespace(
        role_observations=[],
        checkpoint_observations=[checkpoint],
    )

    landmark = build_mobile_timeline_landmarks(evidence)[0]

    assert landmark.seconds == 30.0
    assert not hasattr(landmark, "expected_audio_seconds")
    assert not hasattr(landmark, "private_source_path")
