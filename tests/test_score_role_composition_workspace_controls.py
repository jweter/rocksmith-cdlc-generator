from __future__ import annotations

from pathlib import Path

import pytest

import rocksmith_cdlc_generator.score_role_composition_workspace_controls as controls_module
from rocksmith_cdlc_generator.score_role_composition_workspace_controls import (
    add_score_composition_track,
    compose_role_composition_from_workspace,
    present_score_role_composition_workspace_status,
    remove_score_composition_track,
)
from rocksmith_cdlc_generator.score_role_composition_workspace_status import (
    ScoreRoleCompositionWorkspaceItem,
    ScoreRoleCompositionWorkspaceStatus,
)
from rocksmith_cdlc_generator.score_source import ArrangementRole


def _item(
    arrangement: str,
    *,
    state: str = "single_track",
    is_multi_track: bool = False,
    selected_indices: list[int] | None = None,
    selected_names: list[str | None] | None = None,
    available_indices: list[int] | None = None,
    available_names: list[str | None] | None = None,
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
        available_source_track_indices=available_indices or [],
        available_source_track_names=available_names or [],
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


def test_presented_control_exposes_available_and_removable_tracks() -> None:
    status = ScoreRoleCompositionWorkspaceStatus(
        roles=[
            _item(
                "rhythm",
                state="multi_track_pending",
                is_multi_track=True,
                selected_indices=[1, 3],
                selected_names=["Rhythm 1", "Rhythm 2"],
                available_indices=[0, 2],
                available_names=["Lead", "Bass"],
                overlap_count=0,
            )
        ]
    )

    presented = present_score_role_composition_workspace_status(status)

    control = presented.control_for("rhythm")
    assert control is not None
    assert control.selected_track_indices == [1, 3]
    assert [option.source_track_index for option in control.available_tracks] == [0, 2]
    assert [option.label for option in control.available_tracks] == ["Lead (track 0)", "Bass (track 2)"]
    # The primary (index 1, first selected) is never removable; only the added track is.
    assert control.removable_track_indices == [3]
    assert control.add_track_enabled is True


def test_unmapped_role_never_allows_adding_a_track() -> None:
    status = ScoreRoleCompositionWorkspaceStatus(
        roles=[
            _item(
                "bass",
                state="unmapped",
                selected_indices=[],
                selected_names=[],
                available_indices=[0, 1, 2, 3],
                available_names=["Lead", "Rhythm 1", "Bass", "Rhythm 2"],
                blockers=["bass has no human-confirmed primary score mapping yet"],
            )
        ]
    )

    presented = present_score_role_composition_workspace_status(status)

    control = presented.control_for("bass")
    assert control is not None
    assert control.add_track_enabled is False


def test_add_track_rejects_when_add_disabled(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    status = ScoreRoleCompositionWorkspaceStatus(roles=[_item("lead", state="unmapped", selected_indices=[], selected_names=[])])
    monkeypatch.setattr(
        controls_module, "inspect_score_role_composition_workspace_status", lambda _project: status
    )

    with pytest.raises(ValueError, match="Cannot add a track"):
        add_score_composition_track(tmp_path, arrangement="lead", track_index=0)


def test_add_track_rejects_when_track_already_selected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    status = ScoreRoleCompositionWorkspaceStatus(
        roles=[
            _item(
                "rhythm",
                state="multi_track_pending",
                is_multi_track=True,
                selected_indices=[1, 3],
                selected_names=["Rhythm 1", "Rhythm 2"],
                available_indices=[0],
                available_names=["Lead"],
                overlap_count=0,
            )
        ]
    )
    monkeypatch.setattr(
        controls_module, "inspect_score_role_composition_workspace_status", lambda _project: status
    )

    with pytest.raises(ValueError, match="already selected"):
        add_score_composition_track(tmp_path, arrangement="rhythm", track_index=3)


def test_add_track_rejects_track_not_in_available_list(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    status = ScoreRoleCompositionWorkspaceStatus(
        roles=[
            _item(
                "lead",
                state="single_track",
                selected_indices=[0],
                selected_names=["Lead"],
                available_indices=[2],
                available_names=["Bass"],
            )
        ]
    )
    monkeypatch.setattr(
        controls_module, "inspect_score_role_composition_workspace_status", lambda _project: status
    )

    with pytest.raises(ValueError, match="not an available score track"):
        add_score_composition_track(tmp_path, arrangement="lead", track_index=99)


def test_add_track_persists_merged_selection_across_roles(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    initial = ScoreRoleCompositionWorkspaceStatus(
        roles=[
            _item(
                "lead",
                state="single_track",
                selected_indices=[0],
                selected_names=["Lead"],
                available_indices=[2],
                available_names=["Bass"],
            )
        ]
    )
    refreshed = ScoreRoleCompositionWorkspaceStatus(
        roles=[
            _item(
                "lead",
                state="multi_track_pending",
                is_multi_track=True,
                selected_indices=[0, 2],
                selected_names=["Lead", "Bass"],
                overlap_count=0,
            )
        ]
    )
    statuses = iter([initial, refreshed])
    monkeypatch.setattr(
        controls_module, "inspect_score_role_composition_workspace_status", lambda _project: next(statuses)
    )

    class _ExistingSelection:
        role = ArrangementRole.rhythm
        source_track_indices = [1]

    class _ExistingPlan:
        selections = [_ExistingSelection()]

    monkeypatch.setattr(
        controls_module, "load_current_score_role_composition", lambda _project: _ExistingPlan()
    )

    captured: dict[str, dict] = {}

    def _fake_record(_project, *, selections):
        captured["selections"] = selections
        return None

    monkeypatch.setattr(controls_module, "record_score_role_composition", _fake_record)

    refreshed_controls = add_score_composition_track(tmp_path, arrangement="lead", track_index=2)

    # The unrelated rhythm role's already-persisted selection is preserved untouched.
    assert captured["selections"][ArrangementRole.rhythm] == [1]
    assert captured["selections"][ArrangementRole.lead] == [0, 2]
    control = refreshed_controls.control_for("lead")
    assert control is not None
    assert control.selected_track_indices == [0, 2]


def test_remove_track_rejects_when_not_removable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    status = ScoreRoleCompositionWorkspaceStatus(
        roles=[_item("lead", state="single_track", selected_indices=[0], selected_names=["Lead"])]
    )
    monkeypatch.setattr(
        controls_module, "inspect_score_role_composition_workspace_status", lambda _project: status
    )

    with pytest.raises(ValueError, match="cannot be removed"):
        remove_score_composition_track(tmp_path, arrangement="lead", track_index=0)


def test_remove_track_persists_selection_without_the_removed_track(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pending = ScoreRoleCompositionWorkspaceStatus(
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
    after = ScoreRoleCompositionWorkspaceStatus(
        roles=[_item("rhythm", state="single_track", selected_indices=[1], selected_names=["Rhythm 1"])]
    )
    statuses = iter([pending, after])
    monkeypatch.setattr(
        controls_module, "inspect_score_role_composition_workspace_status", lambda _project: next(statuses)
    )
    monkeypatch.setattr(controls_module, "load_current_score_role_composition", lambda _project: None)

    captured: dict[str, dict] = {}

    def _fake_record(_project, *, selections):
        captured["selections"] = selections
        return None

    monkeypatch.setattr(controls_module, "record_score_role_composition", _fake_record)

    refreshed_controls = remove_score_composition_track(tmp_path, arrangement="rhythm", track_index=3)

    assert captured["selections"][ArrangementRole.rhythm] == [1]
    control = refreshed_controls.control_for("rhythm")
    assert control is not None
    assert control.state == "single_track"
