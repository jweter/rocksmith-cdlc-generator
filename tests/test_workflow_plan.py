from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import rocksmith_cdlc_generator.workflow_plan as workflow_plan


def _inventory(project: Path, **overrides):
    values = {
        "project_path": str(project),
        "local_sources": [],
        "local_audio_sources": 1,
        "unresolved_rights_reviews": 0,
        "reference_count": 0,
        "selected_reference": False,
        "reviewed_recording_context": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_plan_starts_with_automatic_normalization_when_source_is_ready(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "song"
    project.mkdir()
    monkeypatch.setattr(workflow_plan, "build_project_source_inventory", lambda _: _inventory(project))

    plan = workflow_plan.build_project_workflow_plan(project)

    assert plan.next_step_id == "normalize"
    normalize = next(step for step in plan.steps if step.step_id == "normalize")
    assert normalize.status == "ready"
    assert normalize.mode == "automatic"
    assert normalize.command and "cdlc normalize" in normalize.command


def test_plan_keeps_rights_confirmation_as_human_blocker(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "song"
    project.mkdir()
    monkeypatch.setattr(
        workflow_plan,
        "build_project_source_inventory",
        lambda _: _inventory(project, unresolved_rights_reviews=1),
    )

    plan = workflow_plan.build_project_workflow_plan(project)

    assert plan.next_step_id == "source-rights"
    rights = next(step for step in plan.steps if step.step_id == "source-rights")
    assert rights.status == "blocked"
    assert rights.mode == "human"
    assert plan.human_blocking_steps >= 1


def test_single_tab_source_becomes_automatic_alignment_and_reconciliation(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "song"
    (project / "analysis").mkdir(parents=True)
    (project / "analysis" / "tempo_map.json").write_text("{}", encoding="utf-8")
    (project / "analysis" / "bass_raw.json").write_text("{}", encoding="utf-8")
    source = SimpleNamespace(
        family="notation",
        parser_pending=False,
        output_relative_path="sources/imported/song.json",
    )
    monkeypatch.setattr(
        workflow_plan,
        "build_project_source_inventory",
        lambda _: _inventory(project, local_sources=[source]),
    )

    plan = workflow_plan.build_project_workflow_plan(project)

    align = next(step for step in plan.steps if step.step_id == "align-tab")
    reconcile = next(step for step in plan.steps if step.step_id == "reconcile-tab")
    assert align.status == "ready"
    assert align.mode == "automatic"
    assert align.command and "align-source" in align.command
    assert reconcile.status == "blocked"
    assert reconcile.mode == "automatic"


def test_multiple_tab_sources_require_human_source_choice(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "song"
    project.mkdir()
    sources = [
        SimpleNamespace(family="notation", parser_pending=False, output_relative_path="sources/imported/a.json"),
        SimpleNamespace(family="notation", parser_pending=False, output_relative_path="sources/imported/b.json"),
    ]
    monkeypatch.setattr(
        workflow_plan,
        "build_project_source_inventory",
        lambda _: _inventory(project, local_sources=sources),
    )

    plan = workflow_plan.build_project_workflow_plan(project)

    align = next(step for step in plan.steps if step.step_id == "align-tab")
    assert align.status == "blocked"
    assert align.mode == "human"
    assert "2 imported symbolic sources" in align.reason


def test_plan_progresses_to_human_review_after_validation(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "song"
    for relative in [
        "audio/normalized.wav",
        "analysis/tempo_map.json",
        "analysis/bass_raw.json",
        "charts/bass_mapped.json",
        "review/validation_report.json",
    ]:
        path = project / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x", encoding="utf-8")
    monkeypatch.setattr(workflow_plan, "build_project_source_inventory", lambda _: _inventory(project))

    plan = workflow_plan.build_project_workflow_plan(project)

    review = next(step for step in plan.steps if step.step_id == "human-review")
    assert review.status == "ready"
    assert review.mode == "human"
    assert plan.next_step_id == "human-review"
