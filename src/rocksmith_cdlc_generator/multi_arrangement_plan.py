from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from .alignment import AlignmentReport
from .score_mapping_review import load_score_for_mapping_review
from .score_source import ArrangementRole, ProjectScoreSource, ScoreArrangementMapping
from .shared_guitar import shared_guitar_draft_is_current
from .shared_guitar_bounds import shared_guitar_boundary_is_current
from .shared_timeline import load_current_shared_timeline
from .workflow_plan import (
    ProjectWorkflowPlan,
    WorkflowStep,
    _current_score_fanout,
    build_project_workflow_plan,
)


def _confirmed_mappings(score: ProjectScoreSource) -> list[ScoreArrangementMapping]:
    return sorted(
        (mapping for mapping in score.arrangement_mappings if mapping.human_confirmed),
        key=lambda mapping: mapping.role.value,
    )


def _confirmed_guitar_roles(project: Path) -> list[ArrangementRole]:
    try:
        score = load_score_for_mapping_review(project)
        fanout = _current_score_fanout(project, score)
    except (OSError, ValueError, ValidationError):
        return []
    if fanout is None:
        return []

    bass_mapping = score.mapping_for(ArrangementRole.bass)
    bass_entry = next((entry for entry in fanout.arrangements if entry.role is ArrangementRole.bass), None)
    if (
        bass_mapping is None
        or not bass_mapping.human_confirmed
        or bass_entry is None
        or bass_entry.source_track_index != bass_mapping.source_track_index
    ):
        return []

    available = {entry.role for entry in fanout.arrangements}
    return [
        role
        for role in (ArrangementRole.lead, ArrangementRole.rhythm)
        if role in available
        and (mapping := score.mapping_for(role)) is not None
        and mapping.human_confirmed
    ]


def _shared_timeline_is_current(project: Path) -> bool:
    try:
        load_current_shared_timeline(project)
    except (OSError, ValueError, ValidationError):
        return False
    return True


def _guitar_validation_path(project: Path, role: ArrangementRole) -> Path:
    return project / "review" / f"{role.value}_validation_report.json"


def _rebuild_plan(project: Path, steps: list[WorkflowStep]) -> ProjectWorkflowPlan:
    next_step = next((step.step_id for step in steps if step.status in {"blocked", "ready"}), None)
    automatic_ready = sum(step.status == "ready" and step.mode == "automatic" for step in steps)
    human_blocking = sum(step.status == "blocked" and step.mode == "human" for step in steps)
    return ProjectWorkflowPlan(
        project_path=str(project),
        steps=steps,
        next_step_id=next_step,
        automatic_ready_steps=automatic_ready,
        human_blocking_steps=human_blocking,
    )


def _allow_confirmed_subset_fanout(
    project: Path,
    steps: list[WorkflowStep],
    score: ProjectScoreSource,
) -> list[WorkflowStep]:
    """Treat human-confirmed roles as configured and remaining importer proposals as optional.

    A score may legitimately contain only one Rocksmith arrangement. Once at least one
    role has been explicitly confirmed, unconfirmed importer proposals must not force the
    user to map unrelated roles to the same source track merely to satisfy the workflow.
    """

    confirmed = _confirmed_mappings(score)
    if not confirmed:
        return steps

    fanout = _current_score_fanout(project, score)
    roles = ", ".join(mapping.role.value for mapping in confirmed)
    replacement = WorkflowStep(
        step_id="score-arrangements",
        title=(
            "Shared score fanned out to confirmed arrangements"
            if fanout is not None
            else "Fan out confirmed score arrangements"
        ),
        status="complete" if fanout is not None else "ready",
        mode="automatic",
        command=None if fanout is not None else f'cdlc-score-fanout "{project}"',
        reason=(
            f"Current fan-out matches the explicitly confirmed arrangement set: {roles}. "
            "Unconfirmed importer proposals are optional and do not create arrangements."
            if fanout is not None
            else f"Materialize only the explicitly confirmed arrangement set: {roles}. "
            "Unconfirmed importer proposals remain optional and do not block the project."
        ),
    )
    return [replacement if step.step_id == "score-arrangements" else step for step in steps]


def _current_authority_alignment(
    project: Path,
    score: ProjectScoreSource,
    mapping: ScoreArrangementMapping,
    output: Path,
) -> AlignmentReport | None:
    path = project / "analysis" / "alignment.json"
    if not path.is_file():
        return None
    try:
        report = AlignmentReport.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, ValidationError):
        return None
    if Path(report.source_path).expanduser().resolve() != output.resolve():
        return None
    if report.source_sha256 != score.source_sha256:
        return None
    if report.track_index != mapping.source_track_index:
        return None
    return report


def _build_guitar_only_plan(
    project: Path,
    base_steps: list[WorkflowStep],
    score: ProjectScoreSource,
) -> ProjectWorkflowPlan:
    """Build a valid Lead-only/Rhythm-only path without inventing a Bass arrangement."""

    fanout = _current_score_fanout(project, score)
    if fanout is None:
        return _rebuild_plan(project, base_steps)

    confirmed = _confirmed_mappings(score)
    guitar_mappings = [
        mapping
        for mapping in confirmed
        if mapping.role in {ArrangementRole.lead, ArrangementRole.rhythm}
    ]
    if not guitar_mappings:
        return _rebuild_plan(project, base_steps)

    # Prefer Lead as timing authority when present; Rhythm is equally valid when it is
    # the only configured guitar arrangement. Bass remains preferred by the normal path.
    authority = next(
        (mapping for mapping in guitar_mappings if mapping.role is ArrangementRole.lead),
        guitar_mappings[0],
    )
    entry = next(
        (
            item
            for item in fanout.arrangements
            if item.role is authority.role and item.source_track_index == authority.source_track_index
        ),
        None,
    )
    if entry is None:
        return _rebuild_plan(project, base_steps)
    authority_output = (project / entry.output_json).resolve()
    if not authority_output.is_relative_to(project) or not authority_output.is_file():
        return _rebuild_plan(project, base_steps)

    # Keep all common intake/provenance/normalization/tempo steps, but remove the Bass-only
    # transcription/reconciliation/mapping lane. A one-guitar score must not synthesize an
    # unrelated Bass arrangement just to reach timing review.
    tempo_index = next(
        (index for index, step in enumerate(base_steps) if step.step_id == "tempo"),
        None,
    )
    if tempo_index is None:
        return _rebuild_plan(project, base_steps)
    steps = list(base_steps[: tempo_index + 1])
    tempo_complete = steps[-1].status == "complete"

    alignment = _current_authority_alignment(project, score, authority, authority_output)
    alignment_complete = alignment is not None
    project_q = f'"{project}"'
    source_q = f'"{authority_output}"'
    steps.append(
        WorkflowStep(
            step_id="align-tab",
            title=f"Align {authority.role.value.title()} score to recording",
            status="complete" if alignment_complete else ("ready" if tempo_complete else "blocked"),
            mode="automatic",
            command=(
                None
                if alignment_complete or not tempo_complete
                else (
                    f"cdlc align-source {project_q} --source {source_q} "
                    f"--track-index {authority.source_track_index}"
                )
            ),
            reason=(
                f"The current alignment uses the confirmed {authority.role.value.title()} score track as song-timing authority."
                if alignment_complete
                else (
                    f"This project has no confirmed Bass arrangement. Align the confirmed {authority.role.value.title()} track directly to the recording instead of fabricating Bass authority."
                    if tempo_complete
                    else "Score alignment waits for the recording tempo map."
                )
            ),
        )
    )

    timeline_current = _shared_timeline_is_current(project)
    configured_roles = [mapping.role for mapping in guitar_mappings]
    if timeline_current:
        timeline_step = WorkflowStep(
            step_id="shared-timeline",
            title="Shared song timing reviewed",
            status="complete",
            mode="human",
            reason=(
                "One reviewed score-to-recording timeline is current for the configured arrangement set: "
                + ", ".join(role.value for role in configured_roles)
                + "."
            ),
        )
    elif alignment_complete:
        timeline_step = WorkflowStep(
            step_id="shared-timeline",
            title="Review and promote shared song timing",
            status="blocked",
            mode="human",
            command=f"cdlc-shared-timeline promote {project_q}",
            reason=(
                f"Review the confirmed {authority.role.value.title()} score alignment once, then promote it as the song timeline for the configured arrangements."
            ),
        )
    else:
        timeline_step = WorkflowStep(
            step_id="shared-timeline",
            title="Establish shared song timing",
            status="blocked",
            mode="automatic",
            reason=f"Shared timing waits for the confirmed {authority.role.value.title()} score track to be aligned to the recording.",
        )
    steps.append(timeline_step)

    guitar_current: dict[ArrangementRole, bool] = {}
    for mapping in guitar_mappings:
        role = mapping.role
        current = (
            timeline_current
            and shared_guitar_draft_is_current(project, role.value)
            and shared_guitar_boundary_is_current(project, role.value)
        )
        guitar_current[role] = current
        steps.append(
            WorkflowStep(
                step_id=f"build-{role.value}",
                title=f"Build {role.value.title()} from shared timeline",
                status="complete" if current else ("ready" if timeline_current else "blocked"),
                mode="automatic",
                command=(
                    None
                    if current or not timeline_current
                    else f"cdlc-build-shared-guitar {project_q} --instrument {role.value}"
                ),
                reason=(
                    f"The current {role.value.title()} draft is bound to the reviewed shared timeline and confirmed score track."
                    if current
                    else (
                        f"Project the confirmed {role.value.title()} score track through the reviewed song timeline."
                        if timeline_current
                        else f"{role.value.title()} construction waits for timing review."
                    )
                ),
            )
        )

    validations_complete = True
    for mapping in guitar_mappings:
        role = mapping.role
        validation_path = _guitar_validation_path(project, role)
        validated = validation_path.is_file() and guitar_current.get(role, False)
        validations_complete = validations_complete and validated
        current = guitar_current.get(role, False)
        steps.append(
            WorkflowStep(
                step_id=f"validate-{role.value}",
                title=f"Validate {role.value.title()} arrangement",
                status="complete" if validated else ("ready" if current else "blocked"),
                mode="automatic",
                command=None if validated else (
                    f"cdlc validate {project_q} --instrument {role.value}" if current else None
                ),
                reason=(
                    f"{role.value.title()} validation/review report exists for the current draft."
                    if validated
                    else (
                        f"Validate the current {role.value.title()} arrangement before human review."
                        if current
                        else f"{role.value.title()} validation waits for a current arrangement draft."
                    )
                ),
            )
        )

    steps.append(
        WorkflowStep(
            step_id="human-review",
            title="Review flagged timing, notes, fingering, and source disagreements",
            status="ready" if validations_complete else "blocked",
            mode="human",
            reason=(
                "Review only the arrangements actually configured for this project; absent Bass/Lead/Rhythm roles are not errors."
            ),
        )
    )
    return _rebuild_plan(project, steps)


def build_multi_arrangement_workflow_plan(project_dir: Path) -> ProjectWorkflowPlan:
    """Plan Bass/Lead/Rhythm independently while sharing one reviewed song timeline.

    Importer proposals are not configuration requirements. Once a human confirms at
    least one score role, the project may proceed with that subset. The established Bass
    workflow remains unchanged when Bass is configured. When only Lead and/or Rhythm is
    configured, one confirmed guitar track becomes timing authority and the Bass-only
    transcription/reconciliation/mapping lane is omitted.
    """

    base = build_project_workflow_plan(project_dir)
    project = Path(base.project_path).resolve()

    try:
        score = load_score_for_mapping_review(project)
    except (OSError, ValueError, ValidationError):
        return base

    steps = _allow_confirmed_subset_fanout(project, list(base.steps), score)
    confirmed = _confirmed_mappings(score)
    if not confirmed:
        return _rebuild_plan(project, steps)

    bass_mapping = next(
        (mapping for mapping in confirmed if mapping.role is ArrangementRole.bass),
        None,
    )
    if bass_mapping is None:
        return _build_guitar_only_plan(project, steps, score)

    # Existing Bass-authority path: preserve the proven Bass workflow while adding only
    # the guitar roles that the human actually confirmed.
    guitar_roles = _confirmed_guitar_roles(project)
    if not guitar_roles:
        return _rebuild_plan(project, steps)

    align_index = next((index for index, step in enumerate(steps) if step.step_id == "align-tab"), None)
    if align_index is None:
        return _rebuild_plan(project, steps)

    project_q = f'"{project}"'
    alignment_complete = steps[align_index].status == "complete"
    timeline_current = _shared_timeline_is_current(project)

    if timeline_current:
        timeline_step = WorkflowStep(
            step_id="shared-timeline",
            title="Shared song timing reviewed",
            status="complete",
            mode="human",
            reason=(
                "One reviewed score-to-recording timeline is current and is inherited by "
                + ", ".join(role.value for role in guitar_roles)
                + " alongside Bass."
            ),
        )
    elif alignment_complete:
        timeline_step = WorkflowStep(
            step_id="shared-timeline",
            title="Review and promote shared song timing",
            status="blocked",
            mode="human",
            command=f"cdlc-shared-timeline promote {project_q}",
            reason=(
                "The authoritative shared-score Bass projection is aligned. Review that timing once, "
                "then promote it so only the human-confirmed arrangements inherit one song timeline."
            ),
        )
    else:
        timeline_step = WorkflowStep(
            step_id="shared-timeline",
            title="Establish shared song timing",
            status="blocked",
            mode="automatic",
            reason="Shared timing waits for the authoritative shared-score Bass projection to be aligned to the recording.",
        )

    guitar_steps: list[WorkflowStep] = []
    guitar_current: dict[ArrangementRole, bool] = {}
    for role in guitar_roles:
        current = (
            timeline_current
            and shared_guitar_draft_is_current(project, role.value)
            and shared_guitar_boundary_is_current(project, role.value)
        )
        guitar_current[role] = current
        guitar_steps.append(
            WorkflowStep(
                step_id=f"build-{role.value}",
                title=f"Build {role.value.title()} from shared timeline",
                status="complete" if current else ("ready" if timeline_current else "blocked"),
                mode="automatic",
                command=(
                    None
                    if current or not timeline_current
                    else f"cdlc-build-shared-guitar {project_q} --instrument {role.value}"
                ),
                reason=(
                    f"The current {role.value.title()} draft is provenance-bound to the reviewed shared timeline, confirmed score track, and current recording-boundary algorithm."
                    if current
                    else (
                        f"Project the human-confirmed {role.value.title()} score track through the already reviewed shared song timeline and enforce the current recording boundary; no second alignment is required."
                        if timeline_current
                        else f"{role.value.title()} construction waits for the shared song timeline review."
                    )
                ),
            )
        )

    insertion = align_index + 1
    steps[insertion:insertion] = [timeline_step, *guitar_steps]

    human_review_index = next((index for index, step in enumerate(steps) if step.step_id == "human-review"), None)
    if human_review_index is not None:
        validation_steps: list[WorkflowStep] = []
        for role in guitar_roles:
            validation_path = _guitar_validation_path(project, role)
            validated = validation_path.is_file() and guitar_current.get(role, False)
            current = guitar_current.get(role, False)
            validation_steps.append(
                WorkflowStep(
                    step_id=f"validate-{role.value}",
                    title=f"Validate {role.value.title()} arrangement",
                    status="complete" if validated else ("ready" if current else "blocked"),
                    mode="automatic",
                    command=None if validated else (
                        f"cdlc validate {project_q} --instrument {role.value}" if current else None
                    ),
                    reason=(
                        f"{role.value.title()} validation/review report exists for the current bounded draft."
                        if validated
                        else (
                            f"Run arrangement-specific validation for the current bounded {role.value.title()} draft before entering combined human review."
                            if current
                            else f"{role.value.title()} validation waits for a current shared-timeline draft."
                        )
                    ),
                )
            )
        steps[human_review_index:human_review_index] = validation_steps

    return _rebuild_plan(project, steps)
