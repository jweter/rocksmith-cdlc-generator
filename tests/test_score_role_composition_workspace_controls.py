from __future__ import annotations

from pathlib import Path

import pytest

import rocksmith_cdlc_generator.score_role_composition_workspace_controls as controls_module
from rocksmith_cdlc_generator.score_role_composition_workspace_controls import (
    compose_role_composition_from_workspace,
    present_score_role_composition_workspace_status,
)
from rocksmith_cdlc_generator.score_role_composition_workspace_status import (
    ScoreRoleCompositionWorkspaceItem,
    ScoreRoleCompositionWorkspaceStatus,
)


def _item(
    arrangement: str,
    *,
    state: str = "single_track",
    is_multi_track: bool = False,
    selected_indices: list[int] | None = None,
    selected_names: list[str | None] | None = None,
    overlap_count: int | None = None,
    blockers: list[str] | None = None,
) -> ScoreRoleCompositionWorkspaceItem:
    indices = selected_indices if selected_indices is not None else [0]
    names = selected_names if selected_names is not None else [f"{arrangement.title()} Track"]
    return ScoreRoleCompositionWorkspaceItem(
        arrangement=arrangement,
        primary_source_track_index=indices[0] if indices else None,
        primary_source_track_name=names[0] if names else None,
        selected_source_track_indices=indices,
        selected_source_track_names=names,
        is_multi_track=is_multi_track,
        state=state,
        overlap_count=overlap_count,
        blockers=blockers or [],
    )


def test_unmapped_role_disables_compose() -> None:
    status = ScoreRoleCompositionWorkspaceStatus(
        roles=[
            _item(
                "bass",
                state="unmapped",
                selected_indices=[],
                selected_names=[],
                blockers=["bass has no human-confirmed primary score mapping yet"],
            )
        ]
    )

    presented = present_score_role_composition_workspace_status(status)

    control = presented.control_for("bass")
    assert control is not None
    assert control.compose_button_enabled is False
    assert "no human-confirmed primary score mapping" in control.status_text


def test_single_track_role_disables_compose() -> None:
    status = ScoreRoleCompositionWorkspaceStatus(roles=[_item("lead", state="single_track")])

    presented = present_score_role_composition_workspace_status(status)

    control = presented.control_for("lead")
    assert control is not None
    assert control.compose_button_enabled is False
    assert "nothing to compose" in control.status_text


def test_pending_role_with_no_overlaps_enables_compose() -> None:
    status = ScoreRoleCompositionWorkspaceStatus(
        roles=[
            _item(
                "rhythm",
                state="multi_track_pending",
                is_multi_track=True,
                selected_indices=[1, 3],
                selected_names=["Rhythm 1", "Rhythm 2"],
                overlap_count=0,
            )
        ]
    )

    presented = present_score_role_composition_workspace_status(status)

    control = presented.control_for("rhythm")
    assert control is not None
    assert control.compose_button_enabled is True
    assert control.blocker_text is None
    assert "no overlaps to resolve" in control.status_text


def test_pending_role_with_overlaps_disables_compose_and_names_cli() -> None:
    status = ScoreRoleCompositionWorkspaceStatus(
        roles=[
            _item(
                "rhythm",
                state="multi_track_pending",
                is_multi_track=True,
                selected_indices=[1, 3],
                selected_names=["Rhythm 1", "Rhythm 2"],
                overlap_count=2,
            )
        ]
    )

    presented = present_score_role_composition_workspace_status(status)

    control = presented.control_for("rhythm")
    assert control is not None
    assert control.compose_button_enabled is False
    assert control.overlap_count == 2
    assert control.blocker_text is not None
    assert "cdlc-score-composition" in control.blocker_text


def test_composed_role_reports_composed_and_disables_button() -> None:
    status = ScoreRoleCompositionWorkspaceStatus(
        roles=[
            _item(
                "rhythm",
                state="multi_track_composed",
                is_multi_track=True,
                selected_indices=[1, 3],
                selected_names=["Rhythm 1", "Rhythm 2"],
            )
        ]
    )

    presented = present_score_role_composition_workspace_status(status)

    control = presented.control_for("rhythm")
    assert control is not None
    assert control.compose_button_text == "Composed"
    assert control.compose_button_enabled is False
    assert "already composed" in control.status_text


def test_disabled_controller_action_never_calls_compose(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    writes: list[str] = []
    status = ScoreRoleCompositionWorkspaceStatus(roles=[_item("lead", state="single_track")])
    monkeypatch.setattr(
        controls_module,
        "inspect_score_role_composition_workspace_status",
        lambda _project: status,
    )
    monkeypatch.setattr(
        controls_module,
        "compose_and_persist_score_role_composition_fanout",
        lambda _project, *, role, decisions: writes.append(role.value),
    )

    with pytest.raises(ValueError, match="nothing to compose"):
        compose_role_composition_from_workspace(tmp_path, arrangement="lead")

    assert writes == []


def test_enabled_controller_action_composes_once_and_returns_refreshed_state(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    writes: list[str] = []
    statuses = iter(
        [
            ScoreRoleCompositionWorkspaceStatus(
                roles=[
                    _item(
                        "rhythm",
                        state="multi_track_pending",
                        is_multi_track=True,
                        selected_indices=[1, 3],
                        selected_names=["Rhythm 1", "Rhythm 2"],
                        overlap_count=0,
                    )
                ]
            ),
            ScoreRoleCompositionWorkspaceStatus(
                roles=[
                    _item(
                        "rhythm",
                        state="multi_track_composed",
                        is_multi_track=True,
                        selected_indices=[1, 3],
                        selected_names=["Rhythm 1", "Rhythm 2"],
                    )
                ]
            ),
        ]
    )

    class _FakeScore:
        source_sha256 = "a" * 64
        source_format = "musicxml"

    monkeypatch.setattr(
        controls_module,
        "inspect_score_role_composition_workspace_status",
        lambda _project: next(statuses),
    )
    monkeypatch.setattr(
        controls_module,
        "load_score_for_mapping_review",
        lambda _project: _FakeScore(),
    )
    monkeypatch.setattr(
        controls_module,
        "compose_and_persist_score_role_composition_fanout",
        lambda _project, *, role, decisions: writes.append(role.value),
    )

    refreshed = compose_role_composition_from_workspace(tmp_path, arrangement="rhythm")

    assert writes == ["rhythm"]
    control = refreshed.control_for("rhythm")
    assert control is not None
    assert control.state == "multi_track_composed"
    assert control.compose_button_text == "Composed"
