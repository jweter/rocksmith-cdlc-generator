from __future__ import annotations

from rocksmith_cdlc_generator.song_workspace import (
    ArrangementWorkspaceState,
    SongWorkspaceSnapshot,
    SourceWorkspaceState,
    TimelineWorkspaceState,
)
from rocksmith_cdlc_generator.validation_dashboard import build_validation_dashboard


def _snapshot(*arrangements: ArrangementWorkspaceState) -> SongWorkspaceSnapshot:
    return SongWorkspaceSnapshot(
        project_path="C:/fixture/song",
        project_name="Fixture Song",
        title="Fixture Song",
        duration_seconds=120.0,
        health="IN_PROGRESS",
        progress_percent=50,
        complete_steps=2,
        total_steps=4,
        automatic_ready_steps=0,
        human_blocking_steps=0,
        sources=SourceWorkspaceState(
            recording_sha256="1" * 64,
            recording_reviewed=True,
        ),
        timeline=TimelineWorkspaceState(duration_seconds=120.0),
        arrangements=list(arrangements),
        review_queue=[],
    )


def test_dashboard_prioritizes_invalid_and_failed_configured_arrangements() -> None:
    snapshot = _snapshot(
        ArrangementWorkspaceState(
            role="bass",
            configured=True,
            validation_state="FAIL",
            fail_count=2,
            warning_count=1,
        ),
        ArrangementWorkspaceState(
            role="lead",
            configured=True,
            validation_state="INVALID",
            validation_problem="lead_validation_report.json is unreadable",
        ),
        ArrangementWorkspaceState(
            role="rhythm",
            configured=True,
            validation_state="NOT_RUN",
        ),
    )

    dashboard = build_validation_dashboard(snapshot)

    assert dashboard.configured_count == 3
    assert dashboard.blocked_count == 2
    assert dashboard.validation_needed_count == 1
    assert dashboard.xml_ready_count == 0
    assert dashboard.headline == "2 configured arrangement(s) blocked by validation."
    assert [row.state for row in dashboard.rows] == [
        "BLOCKED",
        "BLOCKED",
        "VALIDATION_NEEDED",
    ]
    assert dashboard.rows[0].next_action.startswith("Resolve 2 validation failure")
    assert dashboard.rows[1].next_action == "lead_validation_report.json is unreadable"


def test_dashboard_distinguishes_validated_from_current_xml_ready() -> None:
    snapshot = _snapshot(
        ArrangementWorkspaceState(
            role="bass",
            configured=True,
            validation_state="PASS",
            export_xml_ready=True,
        ),
        ArrangementWorkspaceState(
            role="lead",
            configured=True,
            validation_state="WARNING",
            warning_count=3,
            export_xml_ready=False,
        ),
        ArrangementWorkspaceState(
            role="rhythm",
            configured=True,
            validation_state="PASS",
            export_xml_ready=True,
        ),
    )

    dashboard = build_validation_dashboard(snapshot)

    assert dashboard.blocked_count == 0
    assert dashboard.validation_needed_count == 0
    assert dashboard.xml_ready_count == 2
    assert dashboard.headline == "All configured arrangements are validated; export work remains."
    assert [row.state for row in dashboard.rows] == ["XML_READY", "VALIDATED", "XML_READY"]
    assert dashboard.rows[1].warning_count == 3


def test_unconfigured_arrangement_does_not_block_dashboard() -> None:
    snapshot = _snapshot(
        ArrangementWorkspaceState(
            role="bass",
            configured=True,
            validation_state="PASS",
            export_xml_ready=True,
        ),
        ArrangementWorkspaceState(
            role="lead",
            configured=False,
            validation_state="INVALID",
            validation_problem="old unrelated artifact",
        ),
        ArrangementWorkspaceState(
            role="rhythm",
            configured=False,
            validation_state="NOT_RUN",
        ),
    )

    dashboard = build_validation_dashboard(snapshot)

    assert dashboard.configured_count == 1
    assert dashboard.blocked_count == 0
    assert dashboard.validation_needed_count == 0
    assert dashboard.xml_ready_count == 1
    assert dashboard.headline == "All configured arrangements are validated and have current Rocksmith XML."
    assert dashboard.rows[1].state == "NOT_CONFIGURED"
    assert dashboard.rows[2].state == "NOT_CONFIGURED"
