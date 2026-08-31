from pathlib import Path
from types import SimpleNamespace

from rocksmith_cdlc_generator.multi_arrangement_plan import (
    _confirmed_guitar_roles,
    build_multi_arrangement_workflow_plan,
)
from rocksmith_cdlc_generator.score_source import ArrangementRole
from rocksmith_cdlc_generator.workflow_plan import ProjectWorkflowPlan, WorkflowStep


def _base_plan(tmp_path: Path, *, align_status: str = "complete") -> ProjectWorkflowPlan:
    project = tmp_path / "song"
    project.mkdir()
    steps = [
        WorkflowStep(
            step_id="recording-audio",
            title="Recording audio available",
            status="complete",
            mode="human",
            reason="ready",
        ),
        WorkflowStep(
            step_id="align-tab",
            title="Align tab/notation to recording",
            status=align_status,
            mode="automatic",
            reason="aligned" if align_status == "complete" else "waiting",
        ),
        WorkflowStep(
            step_id="reconcile-tab",
            title="Reconcile",
            status="ready" if align_status == "complete" else "blocked",
            mode="automatic",
            command="cdlc reconcile-bass fixture --source fixture" if align_status == "complete" else None,
            reason="next",
        ),
    ]
    return ProjectWorkflowPlan(
        project_path=str(project),
        steps=steps,
        next_step_id="reconcile-tab" if align_status == "complete" else "align-tab",
        automatic_ready_steps=1 if align_status == "complete" else 0,
        human_blocking_steps=0,
    )


def _full_confirmed_score():
    mappings = [
        SimpleNamespace(role=ArrangementRole.bass, source_track_index=1, human_confirmed=True),
        SimpleNamespace(role=ArrangementRole.lead, source_track_index=2, human_confirmed=True),
        SimpleNamespace(role=ArrangementRole.rhythm, source_track_index=3, human_confirmed=True),
    ]
    return SimpleNamespace(
        arrangement_mappings=mappings,
        mapping_for=lambda role: next((mapping for mapping in mappings if mapping.role is role), None),
    )


def _patch_explicit_score_context(monkeypatch) -> None:
    score = _full_confirmed_score()
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.multi_arrangement_plan.load_score_for_mapping_review",
        lambda project: score,
    )
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.multi_arrangement_plan._allow_confirmed_subset_fanout",
        lambda project, steps, score: steps,
    )


def test_planner_exposes_one_shared_timeline_then_lead_and_rhythm(monkeypatch, tmp_path: Path) -> None:
    base = _base_plan(tmp_path)
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.multi_arrangement_plan.build_project_workflow_plan",
        lambda project: base,
    )
    _patch_explicit_score_context(monkeypatch)
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.multi_arrangement_plan._confirmed_guitar_roles",
        lambda project: [ArrangementRole.lead, ArrangementRole.rhythm],
    )
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.multi_arrangement_plan._shared_timeline_is_current",
        lambda project: True,
    )
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.multi_arrangement_plan.shared_guitar_draft_is_current",
        lambda project, role: False,
    )
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.multi_arrangement_plan.shared_guitar_boundary_is_current",
        lambda project, role: True,
    )

    plan = build_multi_arrangement_workflow_plan(Path(base.project_path))
    ids = [step.step_id for step in plan.steps]

    assert ids == ["recording-audio", "align-tab", "shared-timeline", "build-lead", "build-rhythm", "reconcile-tab"]
    shared = next(step for step in plan.steps if step.step_id == "shared-timeline")
    lead = next(step for step in plan.steps if step.step_id == "build-lead")
    rhythm = next(step for step in plan.steps if step.step_id == "build-rhythm")
    assert shared.status == "complete"
    assert lead.status == rhythm.status == "ready"
    assert lead.command.endswith("--instrument lead")
    assert rhythm.command.endswith("--instrument rhythm")
    assert "align-source" not in lead.command
    assert "align-source" not in rhythm.command


def test_planner_stops_once_for_human_shared_timeline_review(monkeypatch, tmp_path: Path) -> None:
    base = _base_plan(tmp_path)
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.multi_arrangement_plan.build_project_workflow_plan",
        lambda project: base,
    )
    _patch_explicit_score_context(monkeypatch)
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.multi_arrangement_plan._confirmed_guitar_roles",
        lambda project: [ArrangementRole.lead, ArrangementRole.rhythm],
    )
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.multi_arrangement_plan._shared_timeline_is_current",
        lambda project: False,
    )

    plan = build_multi_arrangement_workflow_plan(Path(base.project_path))
    shared = next(step for step in plan.steps if step.step_id == "shared-timeline")
    lead = next(step for step in plan.steps if step.step_id == "build-lead")

    assert shared.status == "blocked"
    assert shared.mode == "human"
    assert shared.command.startswith("cdlc-shared-timeline promote")
    assert lead.status == "blocked"
    assert plan.next_step_id == "shared-timeline"


def test_human_review_waits_for_guitar_validation_even_when_bass_already_validated(
    monkeypatch, tmp_path: Path
) -> None:
    # The inherited Bass-only human-review step's status only reflects Bass's own
    # review/validation_report.json artifact. Once Lead/Rhythm are confirmed and
    # validate-lead/validate-rhythm steps are inserted ahead of it, human-review must
    # not still read as "ready" (and therefore count as progress-complete in
    # song_readiness.build_song_readiness) while a required guitar-role validation is
    # still outstanding.
    project = tmp_path / "song"
    project.mkdir()
    steps = [
        WorkflowStep(
            step_id="recording-audio", title="Recording audio available",
            status="complete", mode="human", reason="ready",
        ),
        WorkflowStep(
            step_id="align-tab", title="Align tab/notation to recording",
            status="complete", mode="automatic", reason="aligned",
        ),
        WorkflowStep(
            step_id="reconcile-tab", title="Reconcile",
            status="complete", mode="automatic", reason="reconciled",
        ),
        WorkflowStep(
            step_id="validate", title="Validate",
            status="complete", mode="automatic", reason="Bass validated",
        ),
        WorkflowStep(
            step_id="human-review",
            title="Review flagged timing, notes, fingering, and source disagreements",
            status="ready",
            mode="human",
            reason="Bass validation/review report exists.",
        ),
    ]
    base = ProjectWorkflowPlan(
        project_path=str(project),
        steps=steps,
        next_step_id="human-review",
        automatic_ready_steps=0,
        human_blocking_steps=0,
    )
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.multi_arrangement_plan.build_project_workflow_plan",
        lambda p: base,
    )
    _patch_explicit_score_context(monkeypatch)
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.multi_arrangement_plan._confirmed_guitar_roles",
        lambda project: [ArrangementRole.lead, ArrangementRole.rhythm],
    )
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.multi_arrangement_plan._shared_timeline_is_current",
        lambda project: True,
    )
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.multi_arrangement_plan.shared_guitar_draft_is_current",
        lambda project, role: True,
    )
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.multi_arrangement_plan.shared_guitar_boundary_is_current",
        lambda project, role: True,
    )

    plan = build_multi_arrangement_workflow_plan(Path(base.project_path))
    review = next(step for step in plan.steps if step.step_id == "human-review")
    lead_validate = next(step for step in plan.steps if step.step_id == "validate-lead")
    rhythm_validate = next(step for step in plan.steps if step.step_id == "validate-rhythm")

    # Guitar drafts are current but no validate-lead/validate-rhythm report exists yet.
    assert lead_validate.status == "ready"
    assert rhythm_validate.status == "ready"
    assert review.status == "blocked"
    assert review.mode == "human"


def test_confirmed_guitar_roles_require_matching_confirmed_bass_authority(monkeypatch, tmp_path: Path) -> None:
    project = tmp_path / "song"
    project.mkdir()

    class FakeScore:
        def mapping_for(self, role):
            if role is ArrangementRole.lead:
                return SimpleNamespace(human_confirmed=True, source_track_index=2)
            if role is ArrangementRole.rhythm:
                return SimpleNamespace(human_confirmed=True, source_track_index=3)
            return None

    monkeypatch.setattr(
        "rocksmith_cdlc_generator.multi_arrangement_plan.load_score_for_mapping_review",
        lambda project: FakeScore(),
    )
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.multi_arrangement_plan._current_score_fanout",
        lambda project, score: SimpleNamespace(
            arrangements=[
                SimpleNamespace(role=ArrangementRole.lead, source_track_index=2),
                SimpleNamespace(role=ArrangementRole.rhythm, source_track_index=3),
            ]
        ),
    )

    assert _confirmed_guitar_roles(project) == []
