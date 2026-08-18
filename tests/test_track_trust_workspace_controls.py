from __future__ import annotations

from pathlib import Path

import pytest

import rocksmith_cdlc_generator.track_trust_workspace_controls as controls_module
from rocksmith_cdlc_generator.track_trust_workspace_controls import (
    accept_track_source_from_workspace,
    present_track_trust_workspace_status,
)
from rocksmith_cdlc_generator.track_trust_workspace_status import (
    TrackTrustWorkspaceItem,
    TrackTrustWorkspaceStatus,
)


def _item(
    arrangement: str,
    *,
    state: str = "unreviewed",
    can_accept: bool = True,
    blockers: list[str] | None = None,
) -> TrackTrustWorkspaceItem:
    return TrackTrustWorkspaceItem(
        arrangement=arrangement,
        source_track_index={"lead": 2, "rhythm": 3, "bass": 1}[arrangement],
        source_track_name=f"{arrangement.title()} Track",
        note_count=12,
        review_state=state,
        can_accept=can_accept,
        blockers=blockers or [],
    )


def test_presenter_exposes_explicit_scope_and_state_specific_actions() -> None:
    status = TrackTrustWorkspaceStatus(
        stale_review_detail="fan-out content changed",
        tracks=[
            _item("lead", state="current"),
            _item("rhythm", state="stale"),
            _item("bass", state="unreviewed"),
        ],
    )

    presented = present_track_trust_workspace_status(status)

    assert presented.stale_review_detail == "fan-out content changed"
    assert [item.arrangement for item in presented.controls] == ["lead", "rhythm", "bass"]
    assert presented.control_for("lead").button_text == "Reaccept Track Source"
    assert presented.control_for("rhythm").button_text == "Reaccept Current Track Source"
    assert presented.control_for("bass").button_text == "Accept Track Source"
    assert all(
        item.acceptance_scope == "imported_note_identity_and_positions"
        for item in presented.controls
    )


def test_presenter_surfaces_blockers_and_disables_ineligible_action() -> None:
    presented = present_track_trust_workspace_status(
        TrackTrustWorkspaceStatus(
            tracks=[
                _item(
                    "lead",
                    can_accept=False,
                    blockers=[
                        "2 event(s) have unresolved string/fret positions",
                        "1 event(s) have position/pitch conflicts",
                    ],
                )
            ]
        )
    )

    control = presented.control_for("lead")
    assert control is not None
    assert control.button_enabled is False
    assert control.blocker_text == (
        "2 event(s) have unresolved string/fret positions; "
        "1 event(s) have position/pitch conflicts"
    )


def test_disabled_controller_action_never_calls_acceptance_write(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    writes: list[str] = []
    status = TrackTrustWorkspaceStatus(
        tracks=[
            _item(
                "lead",
                can_accept=False,
                blockers=["3 event(s) have unresolved string/fret positions"],
            )
        ]
    )
    monkeypatch.setattr(
        controls_module,
        "inspect_track_trust_workspace_status",
        lambda _project: status,
    )
    monkeypatch.setattr(
        controls_module,
        "record_track_source_trust_acceptance",
        lambda _project, *, arrangement: writes.append(arrangement),
    )

    with pytest.raises(ValueError, match="3 event\(s\) have unresolved string/fret positions"):
        accept_track_source_from_workspace(tmp_path, arrangement="lead")

    assert writes == []


def test_enabled_controller_action_records_once_and_returns_refreshed_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    writes: list[str] = []
    statuses = iter(
        [
            TrackTrustWorkspaceStatus(tracks=[_item("lead", state="unreviewed")]),
            TrackTrustWorkspaceStatus(tracks=[_item("lead", state="current")]),
        ]
    )
    monkeypatch.setattr(
        controls_module,
        "inspect_track_trust_workspace_status",
        lambda _project: next(statuses),
    )
    monkeypatch.setattr(
        controls_module,
        "record_track_source_trust_acceptance",
        lambda _project, *, arrangement: writes.append(arrangement),
    )

    refreshed = accept_track_source_from_workspace(tmp_path, arrangement="lead")

    assert writes == ["lead"]
    control = refreshed.control_for("lead")
    assert control is not None
    assert control.review_state == "current"
    assert control.button_text == "Reaccept Track Source"
