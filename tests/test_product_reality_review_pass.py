from __future__ import annotations

import json
from pathlib import Path

from rocksmith_cdlc_generator import multi_arrangement_plan as multi
from rocksmith_cdlc_generator.score_source import ArrangementRole
from rocksmith_cdlc_generator.song_workspace import _read_validation
from rocksmith_cdlc_generator.workflow_plan import ProjectWorkflowPlan, WorkflowStep


def test_legacy_detailed_validation_report_is_grouped_at_workspace_read_time(tmp_path: Path) -> None:
    path = tmp_path / "validation_report.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "status": "WARNING",
                "can_package": True,
                "fail_count": 0,
                "warning_count": 3,
                "review_queue": [
                    {
                        "code": "source_pitch_conflict",
                        "severity": "WARNING",
                        "stage": "reconciliation",
                        "message": "Symbolic and audio-derived notes occur together but disagree on MIDI pitch.",
                        "time_seconds": when,
                        "priority": 90,
                    }
                    for when in (17.845, 18.849, 21.902)
                ],
            }
        ),
        encoding="utf-8",
    )

    report, problem = _read_validation(path)

    assert problem is None
    assert report is not None
    assert report.warning_count == 3
    assert report.fail_count == 0
    assert report.can_package is True
    assert len(report.review_queue) == 1
    assert report.review_queue[0].code == "source_pitch_conflict"
    assert report.review_queue[0].time_seconds == 17.845
    assert report.review_queue[0].message.startswith("3 occurrences. Example:")


def test_workspace_grouping_keeps_failures_individual(tmp_path: Path) -> None:
    path = tmp_path / "validation_report.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "status": "FAIL",
                "can_package": False,
                "fail_count": 2,
                "warning_count": 0,
                "review_queue": [
                    {
                        "code": "unmapped_bass_note",
                        "severity": "FAIL",
                        "stage": "mapping",
                        "message": f"Bass note {index} has no playable string/fret position.",
                        "time_seconds": 10.0 + index,
                        "priority": 100,
                    }
                    for index in range(2)
                ],
            }
        ),
        encoding="utf-8",
    )

    report, problem = _read_validation(path)

    assert problem is None
    assert report is not None
    assert len(report.review_queue) == 2
    assert all(item.severity == "FAIL" for item in report.review_queue)


def test_guitar_validation_precedes_combined_human_review(tmp_path: Path, monkeypatch) -> None:
    base = ProjectWorkflowPlan(
        project_path=str(tmp_path),
        steps=[
            WorkflowStep(
                step_id="align-tab",
                title="Align tab/notation to recording",
                status="complete",
                mode="automatic",
                reason="aligned",
            ),
            WorkflowStep(
                step_id="validate",
                title="Run unified validation and build review queue",
                status="complete",
                mode="automatic",
                reason="Bass validation exists",
            ),
            WorkflowStep(
                step_id="human-review",
                title="Review generated song draft",
                status="ready",
                mode="human",
                reason="Review generated uncertainty",
            ),
        ],
        next_step_id="human-review",
        automatic_ready_steps=0,
        human_blocking_steps=0,
    )

    monkeypatch.setattr(multi, "build_project_workflow_plan", lambda _project: base)
    monkeypatch.setattr(
        multi,
        "_confirmed_guitar_roles",
        lambda _project: [ArrangementRole.lead, ArrangementRole.rhythm],
    )
    monkeypatch.setattr(multi, "_shared_timeline_is_current", lambda _project: True)
    monkeypatch.setattr(multi, "shared_guitar_draft_is_current", lambda _project, _role: True)
    monkeypatch.setattr(multi, "shared_guitar_boundary_is_current", lambda _project, _role: True)

    plan = multi.build_multi_arrangement_workflow_plan(tmp_path)
    ids = [step.step_id for step in plan.steps]

    assert ids.index("validate-lead") < ids.index("human-review")
    assert ids.index("validate-rhythm") < ids.index("human-review")
    assert next(step for step in plan.steps if step.step_id == "validate-lead").command.endswith("--instrument lead")
    assert next(step for step in plan.steps if step.step_id == "validate-rhythm").command.endswith("--instrument rhythm")
    assert plan.next_step_id == "validate-lead"
    assert plan.automatic_ready_steps == 2
