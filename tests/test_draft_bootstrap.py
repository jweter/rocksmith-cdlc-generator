from __future__ import annotations

from pathlib import Path

import pytest

from rocksmith_cdlc_generator import draft_bootstrap
from rocksmith_cdlc_generator.project_score import RegisteredProjectScore
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


def _registered(project: Path) -> RegisteredProjectScore:
    return RegisteredProjectScore(
        project_path=str(project),
        stored_source_path=str(project / "sources" / "score" / "original" / "song.gp5"),
        score_source_path=str(project / "sources" / "score" / "source.json"),
        intake_receipt_path=str(project / "sources" / "intake" / "score.json"),
        human_rights_review_required=True,
    )


def test_bootstrap_registers_complete_score_before_bass_import_then_runs_auto(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    audio = tmp_path / "Artist - Song.flac"
    notation = tmp_path / "Song.gp5"
    audio.write_bytes(b"audio")
    notation.write_bytes(b"tab")
    project = tmp_path / "projects" / "artist-song"
    project.mkdir(parents=True)
    (project / "project.json").write_text("{}", encoding="utf-8")

    events: list[str] = []
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
        events.append("bass_import")
        return AddSourceResult(
            status="complete",
            route=route,
            output_path=str(project / "sources" / "imported" / "tab.json"),
            intake_receipt_path=str(project / "sources" / "intake" / "tab.json"),
            human_rights_review_required=False,
        )

    def fake_register(project_dir: Path, source: Path, **kwargs):
        assert project_dir == project.resolve()
        assert source == notation.resolve()
        assert kwargs["rights_class"] is SourceRightsClass.user_owned_local
        events.append("score_registration")
        return _registered(project.resolve())

    monkeypatch.setattr(draft_bootstrap, "add_local_source", fake_add)
    monkeypatch.setattr(draft_bootstrap, "register_project_score", fake_register)
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
    assert result.score_source_path == str(project / "sources" / "score" / "source.json")
    assert result.automatic_run.stop_reason == "human_gate"
    assert events == ["score_registration", "bass_import"]
    assert calls == [
        ("Artist - Song.flac", None, SourceRightsClass.user_owned_local),
        ("Song.gp5", project.resolve(), SourceRightsClass.user_owned_local),
    ]


def test_notation_failure_preserves_registered_score_and_created_project_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    audio = tmp_path / "song.flac"
    notation = tmp_path / "ambiguous.gp5"
    audio.write_bytes(b"audio")
    notation.write_bytes(b"tab")
    project = tmp_path / "projects" / "song"
    project.mkdir(parents=True)
    (project / "project.json").write_text("{}", encoding="utf-8")
    registered = False

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

    def fake_register(project_dir: Path, source: Path, **kwargs):
        nonlocal registered
        registered = True
        return _registered(project_dir)

    monkeypatch.setattr(draft_bootstrap, "add_local_source", fake_add)
    monkeypatch.setattr(draft_bootstrap, "register_project_score", fake_register)

    with pytest.raises(draft_bootstrap.DraftBootstrapError) as exc_info:
        draft_bootstrap.create_and_run_first_draft(audio, notation=notation)

    assert registered is True
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
