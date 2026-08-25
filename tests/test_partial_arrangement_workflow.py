from __future__ import annotations

from pathlib import Path

import pytest

from rocksmith_cdlc_generator import multi_arrangement_plan
from rocksmith_cdlc_generator.multi_arrangement_plan import build_multi_arrangement_workflow_plan
from rocksmith_cdlc_generator.score_fanout import ScoreFanoutEntry, ScoreFanoutManifest
from rocksmith_cdlc_generator.score_source import (
    ArrangementRole,
    ProjectScoreSource,
    ScoreArrangementMapping,
    ScoreTrackCandidate,
)
from rocksmith_cdlc_generator.shared_timeline import _authority_mapping
from rocksmith_cdlc_generator.workflow_plan import ProjectWorkflowPlan, WorkflowStep


def _score(*, confirm_bass: bool = False, confirm_lead: bool = True) -> ProjectScoreSource:
    return ProjectScoreSource(
        source_filename="single.gp5",
        source_sha256="a" * 64,
        source_format="gp5",
        imported_relative_path="sources/score/single.gp5",
        tracks=[
            ScoreTrackCandidate(
                source_track_index=0,
                name="Guitar",
                instrument_hint="guitar",
                note_count=406,
            )
        ],
        arrangement_mappings=[
            ScoreArrangementMapping(
                role=ArrangementRole.bass,
                source_track_index=0,
                confidence=0.1,
                basis=["importer proposal"],
                human_confirmed=confirm_bass,
            ),
            ScoreArrangementMapping(
                role=ArrangementRole.lead,
                source_track_index=0,
                confidence=0.7,
                basis=["importer proposal"],
                human_confirmed=confirm_lead,
            ),
            ScoreArrangementMapping(
                role=ArrangementRole.rhythm,
                source_track_index=0,
                confidence=0.5,
                basis=["importer proposal"],
                human_confirmed=False,
            ),
        ],
    )


def _base_plan(project: Path) -> ProjectWorkflowPlan:
    steps = [
        WorkflowStep(
            step_id="recording-audio",
            title="Recording audio available",
            status="complete",
            mode="human",
            reason="fixture",
        ),
        WorkflowStep(
            step_id="source-rights",
            title="Local-source rights/provenance reviewed",
            status="complete",
            mode="human",
            reason="fixture",
        ),
        WorkflowStep(
            step_id="score-arrangements",
            title="Confirm proposed score arrangement mappings",
            status="blocked",
            mode="human",
            reason="bass, rhythm still unconfirmed",
        ),
        WorkflowStep(
            step_id="recording-reference",
            title="Reference",
            status="optional",
            mode="human",
            reason="fixture",
        ),
        WorkflowStep(
            step_id="normalize",
            title="Normalize",
            status="complete",
            mode="automatic",
            reason="fixture",
        ),
        WorkflowStep(
            step_id="tempo",
            title="Tempo",
            status="complete",
            mode="automatic",
            reason="fixture",
        ),
        WorkflowStep(
            step_id="transcribe-bass",
            title="Bass transcription",
            status="ready",
            mode="automatic",
            command=f'cdlc transcribe-bass "{project}" --engine librosa-pyin',
            reason="fixture",
        ),
        WorkflowStep(
            step_id="align-tab",
            title="Bass alignment",
            status="optional",
            mode="human",
            reason="fixture",
        ),
        WorkflowStep(
            step_id="map-bass",
            title="Bass map",
            status="ready",
            mode="automatic",
            command=f'cdlc map-bass "{project}" --source auto --tuning "E Standard" --max-fret 24',
            reason="fixture",
        ),
        WorkflowStep(
            step_id="validate",
            title="Bass validation",
            status="blocked",
            mode="automatic",
            reason="fixture",
        ),
        WorkflowStep(
            step_id="human-review",
            title="Human review",
            status="blocked",
            mode="human",
            reason="fixture",
        ),
    ]
    return ProjectWorkflowPlan(
        project_path=str(project),
        steps=steps,
        next_step_id="score-arrangements",
        automatic_ready_steps=2,
        human_blocking_steps=2,
    )


def test_confirmed_lead_makes_unconfirmed_bass_and_rhythm_optional_before_fanout(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project = tmp_path / "song"
    project.mkdir()
    score = _score()

    monkeypatch.setattr(
        multi_arrangement_plan,
        "build_project_workflow_plan",
        lambda _project: _base_plan(project),
    )
    monkeypatch.setattr(
        multi_arrangement_plan,
        "load_score_for_mapping_review",
        lambda _project: score,
    )
    monkeypatch.setattr(multi_arrangement_plan, "_current_score_fanout", lambda _project, _score: None)

    plan = build_multi_arrangement_workflow_plan(project)
    mapping_step = next(step for step in plan.steps if step.step_id == "score-arrangements")

    assert mapping_step.status == "ready"
    assert mapping_step.mode == "automatic"
    assert mapping_step.command == f'cdlc-score-fanout "{project.resolve()}"'
    assert "lead" in mapping_step.reason
    assert "optional" in mapping_step.reason
    assert plan.next_step_id == "score-arrangements"


def test_lead_only_project_omits_bass_pipeline_and_aligns_confirmed_guitar(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project = (tmp_path / "song").resolve()
    project.mkdir()
    output = project / "sources" / "imported" / "lead.json"
    output.parent.mkdir(parents=True)
    output.write_text("{}", encoding="utf-8")

    score = _score()
    fanout = ScoreFanoutManifest(
        score_source_sha256=score.source_sha256,
        score_source_format=score.source_format,
        arrangements=[
            ScoreFanoutEntry(
                role=ArrangementRole.lead,
                source_track_index=0,
                output_json="sources/imported/lead.json",
            )
        ],
    )

    monkeypatch.setattr(
        multi_arrangement_plan,
        "build_project_workflow_plan",
        lambda _project: _base_plan(project),
    )
    monkeypatch.setattr(
        multi_arrangement_plan,
        "load_score_for_mapping_review",
        lambda _project: score,
    )
    monkeypatch.setattr(
        multi_arrangement_plan,
        "_current_score_fanout",
        lambda _project, _score: fanout,
    )
    monkeypatch.setattr(
        multi_arrangement_plan,
        "_current_authority_alignment",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(multi_arrangement_plan, "_shared_timeline_is_current", lambda _project: False)

    plan = build_multi_arrangement_workflow_plan(project)
    ids = [step.step_id for step in plan.steps]
    alignment = next(step for step in plan.steps if step.step_id == "align-tab")

    assert "transcribe-bass" not in ids
    assert "map-bass" not in ids
    assert alignment.status == "ready"
    assert alignment.mode == "automatic"
    assert "--track-index 0" in (alignment.command or "")
    assert "lead.json" in (alignment.command or "")
    assert plan.next_step_id == "align-tab"


def test_shared_timeline_uses_lead_when_no_bass_is_confirmed() -> None:
    score = _score()
    fanout = ScoreFanoutManifest(
        score_source_sha256=score.source_sha256,
        score_source_format=score.source_format,
        arrangements=[
            ScoreFanoutEntry(
                role=ArrangementRole.lead,
                source_track_index=0,
                output_json="sources/imported/lead.json",
            )
        ],
    )

    mapping, entry = _authority_mapping(score, fanout)

    assert mapping.role is ArrangementRole.lead
    assert entry.role is ArrangementRole.lead


def test_shared_timeline_still_prefers_bass_when_bass_is_confirmed() -> None:
    score = _score(confirm_bass=True)
    fanout = ScoreFanoutManifest(
        score_source_sha256=score.source_sha256,
        score_source_format=score.source_format,
        arrangements=[
            ScoreFanoutEntry(
                role=ArrangementRole.bass,
                source_track_index=0,
                output_json="sources/imported/bass.json",
            ),
            ScoreFanoutEntry(
                role=ArrangementRole.lead,
                source_track_index=0,
                output_json="sources/imported/lead.json",
            ),
        ],
    )

    mapping, entry = _authority_mapping(score, fanout)

    assert mapping.role is ArrangementRole.bass
    assert entry.role is ArrangementRole.bass
