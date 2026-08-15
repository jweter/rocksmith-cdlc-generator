from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import rocksmith_cdlc_generator.mapping_pipeline as mapping_pipeline
from rocksmith_cdlc_generator.song_workspace import _workflow_has_required_work
from rocksmith_cdlc_generator.workflow_plan import ProjectWorkflowPlan, WorkflowStep


def _plan(*steps: WorkflowStep) -> ProjectWorkflowPlan:
    return ProjectWorkflowPlan(
        project_path="fixture",
        steps=list(steps),
        next_step_id=None,
        automatic_ready_steps=sum(
            step.status == "ready" and step.mode == "automatic" for step in steps
        ),
        human_blocking_steps=sum(
            step.status == "blocked" and step.mode == "human" for step in steps
        ),
    )


def test_optional_and_ready_human_review_do_not_make_readiness_unreachable() -> None:
    plan = _plan(
        WorkflowStep(
            step_id="done",
            title="Done",
            status="complete",
            mode="automatic",
            reason="fixture",
        ),
        WorkflowStep(
            step_id="recording-reference",
            title="Optional reference",
            status="optional",
            mode="human",
            reason="fixture",
        ),
        WorkflowStep(
            step_id="human-review",
            title="Review flagged notes",
            status="ready",
            mode="human",
            reason="fixture",
        ),
    )

    assert not _workflow_has_required_work(plan)


def test_ready_automatic_or_blocked_step_remains_required_work() -> None:
    automatic = _plan(
        WorkflowStep(
            step_id="export",
            title="Export",
            status="ready",
            mode="automatic",
            reason="fixture",
        )
    )
    blocked = _plan(
        WorkflowStep(
            step_id="repair",
            title="Repair",
            status="blocked",
            mode="automatic",
            reason="fixture",
        )
    )

    assert _workflow_has_required_work(automatic)
    assert _workflow_has_required_work(blocked)


def test_bass_remap_invalidates_validation_xml_and_package_staging(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project = tmp_path / "song"
    for relative in ("analysis", "charts", "review", "eof", "build/dlcbuilder", "build/staging"):
        (project / relative).mkdir(parents=True, exist_ok=True)
    (project / "analysis" / "bass_raw.json").write_text("fixture", encoding="utf-8")

    stale_files = (
        "review/validation_report.json",
        "review/flags.json",
        "review/summary.md",
        "eof/arr_bass_RS2.xml",
        "eof/export_manifest.json",
        "eof/README.md",
        "build/dlcbuilder/stale.txt",
        "build/staging/psarc_receipt.json",
        "build/staging/stale.psarc",
    )
    for relative in stale_files:
        path = project / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("stale", encoding="utf-8")

    monkeypatch.setattr(mapping_pipeline, "resolve_bass_tuning", lambda _name: object())
    monkeypatch.setattr(mapping_pipeline, "read_transcription", lambda _path: object())
    monkeypatch.setattr(
        mapping_pipeline,
        "map_bass_transcription",
        lambda _source, _tuning, *, max_fret: object(),
    )
    monkeypatch.setattr(
        mapping_pipeline,
        "review_bass_mapping",
        lambda _mapping: SimpleNamespace(model_dump_json=lambda indent: '{"review":"current"}'),
    )

    def write_mapping(_mapping, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"mapping":"current"}', encoding="utf-8")

    monkeypatch.setattr(mapping_pipeline, "write_bass_mapping", write_mapping)

    result = mapping_pipeline.map_project_bass(project, source="raw")

    assert result["mapping"].read_text(encoding="utf-8") == '{"mapping":"current"}'
    assert result["review"].read_text(encoding="utf-8") == '{"review":"current"}'
    for relative in stale_files[:6]:
        assert not (project / relative).exists()
    assert not (project / "build" / "dlcbuilder").exists()
    assert not (project / "build" / "staging").exists()
