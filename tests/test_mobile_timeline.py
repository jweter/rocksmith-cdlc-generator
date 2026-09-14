from __future__ import annotations

from types import SimpleNamespace

import pytest

from rocksmith_cdlc_generator.mobile_timeline import build_mobile_timeline_landmarks


def _role(name: str) -> SimpleNamespace:
    return SimpleNamespace(value=name)


def test_mobile_timeline_landmarks_are_deterministic_and_keep_roles_first_class() -> None:
    evidence = SimpleNamespace(
        role_observations=[
            SimpleNamespace(role=_role("rhythm"), first_playable_seconds=8.0),
            SimpleNamespace(role=_role("bass"), first_playable_seconds=7.0),
            SimpleNamespace(role=_role("lead"), first_playable_seconds=7.0),
        ],
        checkpoint_observations=[
            SimpleNamespace(
                role=_role("lead"),
                checkpoint_id="later-lead",
                observed_audio_seconds=77.756,
                expected_audio_seconds=77.75,
            ),
            SimpleNamespace(
                role=_role("bass"),
                checkpoint_id="later-bass",
                observed_audio_seconds=77.756,
                expected_audio_seconds=77.75,
            ),
        ],
    )

    landmarks = build_mobile_timeline_landmarks(evidence)

    assert [(item["arrangement"], item["kind"], item["seconds"]) for item in landmarks] == [
        ("bass", "first_playable", 7.0),
        ("lead", "first_playable", 7.0),
        ("rhythm", "first_playable", 8.0),
        ("bass", "checkpoint", 77.756),
        ("lead", "checkpoint", 77.756),
    ]


def test_mobile_timeline_landmarks_fail_closed_on_nonfinite_timestamp() -> None:
    evidence = SimpleNamespace(
        role_observations=[SimpleNamespace(role=_role("bass"), first_playable_seconds=float("nan"))],
        checkpoint_observations=[],
    )

    with pytest.raises(ValueError, match="invalid mobile timeline timestamp"):
        build_mobile_timeline_landmarks(evidence)
