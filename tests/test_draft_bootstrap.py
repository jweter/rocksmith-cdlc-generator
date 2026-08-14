from __future__ import annotations

from pathlib import Path

import pytest

from rocksmith_cdlc_generator import draft_bootstrap
from rocksmith_cdlc_generator.source_intake import SourceRightsClass
from rocksmith_cdlc_generator.source_router import route_local_source
from rocksmith_cdlc_generator.source_workflow import AddSourceResult
from rocksmith_cdlc_generator.workflow_plan import ProjectWorkflowPlan, WorkflowStep
from rocksmith_cdlc_generator.workflow_runner import AutomaticWorkflowRun


def _run(project: Path, *, stop_reason: str = "human_gate") -> AutomaticWorkflowRun:
    step = WorkflowStep(
        step_id="human-review",
        title="Review generated draft",
        status="blocked",
        mode="human",
        reason="Human musical review remains required.",
    )
    plan = ProjectWorkflowPlan(
        project_path=str(project),
        steps=[step],
        next_step_id="human-review",
        automatic_ready_steps=0,
        human_blocking_steps=1,
    )
    return AutomaticWorkflowRun(
        project_path=str(project),
        executed_steps=[],
        stop_reason=stop_reason,
        next_step_id="human-review",
        final_plan=plan,
    )


def test_bootstrap_creates_project_imports_notation_then_runs_auto(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    audio = tmp_path / "Artist - Song.flac"
    notation = tmp_path / "Song.gp5"
    audio.write_bytes(b"audio")
    notation.write_bytes(b"tab")
    project = tmp_path / "projects" / "artist-song"
    project.mkdir(parents=True)
    (project / "project.json").write_text("{}", encoding="utf-8")

    calls: list[tuple[str, Path | None, SourceRightsClass]] = []

    def fake_add(source: Path, **kwargs):
        rights = kwargs["rights_class"]
        calls.append((source.name, kwargs.get("project"), rights))
        route = route_local_source(source, rights_class=rights)
        if source == audio.resolve():
            return AddSourceResult(
                status="complete",
                route=route,
                output_path=str(project),
                intake_receipt_path=str(project / "sources" / "intake" / "audio.json"),
                human_rights_review_required=False,
            )
        return AddSourceResult(
            status="complete",
            route=route,
            output_path=str(project / "sources" / "imported" / "tab.json"),
            intake_receipt_path=str(project / "sources" / "intake" / "tab.json"),
            human_rights_review_required=False,
        )

    monkeypatch.setattr(draft_bootstrap, "add_local_source", fake_add)
    monkeypatch.setattr(
        draft_bootstrap,
        "run_automatic_first_draft",
        lambda project_dir, max_steps: _run(project_dir),
    )

    result = draft_bootstrap.create_and_run_first_draft(
        audio,
        artist="Artist",
        notation=notation,
        audio_rights_class=SourceRightsClass.user_owned_local,
        notation_rights_class=SourceRightsClass.user_owned_local,
    )

    assert result.title == "Artist - Song"
    assert result.project_path == str(project.resolve())
    assert result.automatic_run.stop_reason == "human_gate"
    assert calls == [
        ("Artist - Song.flac", None, SourceRightsClass.user_owned_local),
        ("Song.gp5", project.resolve(), SourceRightsClass.user_owned_local),
    ]


def test_notation_failure_preserves_created_project_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    audio = tmp_path / "song.flac"
    notation = tmp_path / "ambiguous.gp5"
    audio.write_bytes(b"audio")
    notation.write_bytes(b"tab")
    project = tmp_path / "projects" / "song"
    project.mkdir(parents=True)
    (project / "project.json").write_text("{}", encoding="utf-8")

    def fake_add(source: Path, **kwargs):
        route = route_local_source(source, rights_class=kwargs["rights_class"])
        if kwargs.get("project") is None:
            return AddSourceResult(
                status="complete",
                route=route,
                output_path=str(project),
                intake_receipt_path=None,
                human_rights_review_required=True,
            )
        raise ValueError("multiple Bass tracks require --track-index")

    monkeypatch.setattr(draft_bootstrap, "add_local_source", fake_add)

    with pytest.raises(draft_bootstrap.DraftBootstrapError) as exc_info:
        draft_bootstrap.create_and_run_first_draft(audio, notation=notation)

    assert exc_info.value.stage == "notation_intake"
    assert exc_info.value.project_path == str(project.resolve())
    assert "track-index" in str(exc_info.value)


def test_unknown_rights_are_not_auto_upgraded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    audio = tmp_path / "song.wav"
    audio.write_bytes(b"audio")
    project = tmp_path / "projects" / "song"
    project.mkdir(parents=True)
    (project / "project.json").write_text("{}", encoding="utf-8")
    seen: list[SourceRightsClass] = []

    def fake_add(source: Path, **kwargs):
        rights = kwargs["rights_class"]
        seen.append(rights)
        return AddSourceResult(
            status="complete",
            route=route_local_source(source, rights_class=rights),
            output_path=str(project),
            intake_receipt_path=None,
            human_rights_review_required=True,
        )

    monkeypatch.setattr(draft_bootstrap, "add_local_source", fake_add)
    monkeypatch.setattr(
        draft_bootstrap,
        "run_automatic_first_draft",
        lambda project_dir, max_steps: _run(project_dir),
    )

    result = draft_bootstrap.create_and_run_first_draft(audio)

    assert seen == [SourceRightsClass.unknown]
    assert result.automatic_run.stop_reason == "human_gate"
