from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .beats import read_tempo_map
from .models import ProjectManifest
from .multi_arrangement_plan import build_multi_arrangement_workflow_plan
from .score_mapping_review import load_score_for_mapping_review
from .score_source import ArrangementRole, ProjectScoreSource
from .shared_guitar import shared_guitar_draft_is_current
from .shared_timeline import load_current_shared_timeline
from .source_rights_review import latest_source_rights_reviews
from .validation import ReviewItem, ValidationReport

WorkspaceHealth = Literal["NEW", "IN_PROGRESS", "REVIEW", "BLOCKED", "READY"]
ValidationState = Literal["NOT_RUN", "INVALID", "PASS", "WARNING", "FAIL"]


class WorkspaceReviewItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    arrangement: Literal["bass", "lead", "rhythm"]
    code: str
    severity: Literal["INFO", "WARNING", "FAIL"]
    stage: str
    message: str
    time_seconds: float | None = Field(default=None, ge=0)
    note_index: int | None = Field(default=None, ge=0)
    priority: int = Field(ge=0, le=100)


class ArrangementWorkspaceState(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: Literal["bass", "lead", "rhythm"]
    configured: bool
    score_track_index: int | None = Field(default=None, ge=0)
    mapping_confirmed: bool = False
    draft_state: Literal["MISSING", "PRESENT", "CURRENT"] = "MISSING"
    validation_state: ValidationState = "NOT_RUN"
    validation_problem: str | None = None
    fail_count: int = Field(default=0, ge=0)
    warning_count: int = Field(default=0, ge=0)
    export_xml_ready: bool = False


class TimelineWorkspaceState(BaseModel):
    model_config = ConfigDict(frozen=True)

    duration_seconds: float = Field(ge=0)
    beat_times: list[float] = Field(default_factory=list)
    low_confidence_beats: int = Field(default=0, ge=0)
    shared_timeline_current: bool = False
    shared_timeline_confidence: float | None = Field(default=None, ge=0, le=1)
    shared_timeline_offset_seconds: float | None = None
    shared_anchor_audio_times: list[float] = Field(default_factory=list)
    shared_timeline_problem: str | None = None


class SourceWorkspaceState(BaseModel):
    model_config = ConfigDict(frozen=True)

    recording_sha256: str
    recording_reviewed: bool
    score_filename: str | None = None
    score_format: str | None = None
    score_sha256: str | None = None
    score_track_count: int = Field(default=0, ge=0)
    score_reviewed: bool = False


class SongWorkspaceSnapshot(BaseModel):
    """Read-only product snapshot consumed by the Windows Song Workspace.

    The snapshot deliberately reads existing project contracts and review artifacts. It
    does not promote authorities, accept mappings, rewrite validation state, or otherwise
    turn GUI inspection into an implicit human decision.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    project_path: str
    project_name: str
    artist: str | None = None
    title: str
    duration_seconds: float = Field(ge=0)
    health: WorkspaceHealth
    progress_percent: int = Field(ge=0, le=100)
    complete_steps: int = Field(ge=0)
    total_steps: int = Field(ge=0)
    automatic_ready_steps: int = Field(ge=0)
    human_blocking_steps: int = Field(ge=0)
    next_step_id: str | None = None
    next_action_title: str | None = None
    next_action_reason: str | None = None
    sources: SourceWorkspaceState
    timeline: TimelineWorkspaceState
    arrangements: list[ArrangementWorkspaceState]
    review_queue: list[WorkspaceReviewItem]


def _read_validation(path: Path) -> tuple[ValidationReport | None, str | None]:
    if not path.is_file():
        return None, None
    try:
        return ValidationReport.model_validate_json(path.read_text(encoding="utf-8")), None
    except (OSError, ValueError, ValidationError) as exc:
        return None, (
            f"Validation report '{path.name}' is unreadable or invalid: {exc}. "
            "Re-run validation before trusting export readiness."
        )


def _validation_path(project: Path, role: ArrangementRole) -> Path:
    if role is ArrangementRole.bass:
        return project / "review" / "validation_report.json"
    return project / "review" / f"{role.value}_validation_report.json"


def _export_path(project: Path, role: ArrangementRole) -> Path:
    return project / "eof" / f"arr_{role.value}_RS2.xml"


def _draft_state(project: Path, role: ArrangementRole) -> Literal["MISSING", "PRESENT", "CURRENT"]:
    if role is ArrangementRole.bass:
        mapped = project / "charts" / "bass_mapped.json"
        if mapped.is_file():
            return "CURRENT"
        if (project / "charts" / "bass_reconciled.json").is_file() or (project / "analysis" / "bass_raw.json").is_file():
            return "PRESENT"
        return "MISSING"

    chart = project / "charts" / f"{role.value}_source.json"
    if not chart.is_file():
        return "MISSING"
    if shared_guitar_draft_is_current(project, role.value):
        return "CURRENT"
    return "PRESENT"


def _score_or_none(project: Path) -> ProjectScoreSource | None:
    try:
        return load_score_for_mapping_review(project)
    except (OSError, ValueError, ValidationError, FileNotFoundError):
        return None


def _timeline_snapshot(project: Path, duration: float) -> TimelineWorkspaceState:
    beat_times: list[float] = []
    low_confidence = 0
    tempo_path = project / "analysis" / "tempo_map.json"
    if tempo_path.is_file():
        try:
            tempo = read_tempo_map(tempo_path)
        except (OSError, ValueError, ValidationError):
            tempo = None
        if tempo is not None:
            beat_times = [float(beat.time) for beat in tempo.beats]
            low_confidence = sum(beat.confidence < 0.30 for beat in tempo.beats)

    try:
        shared = load_current_shared_timeline(project)
    except (OSError, ValueError, ValidationError, FileNotFoundError) as exc:
        shared = None
        shared_problem = str(exc) if (project / "analysis" / "shared_timeline.json").is_file() else None
    else:
        shared_problem = None

    return TimelineWorkspaceState(
        duration_seconds=duration,
        beat_times=beat_times,
        low_confidence_beats=low_confidence,
        shared_timeline_current=shared is not None,
        shared_timeline_confidence=shared.confidence if shared is not None else None,
        shared_timeline_offset_seconds=shared.global_offset_seconds if shared is not None else None,
        shared_anchor_audio_times=(
            [float(anchor.audio_time_seconds) for anchor in shared.anchors] if shared is not None else []
        ),
        shared_timeline_problem=shared_problem,
    )


def _source_snapshot(project: Path, manifest: ProjectManifest, score: ProjectScoreSource | None) -> SourceWorkspaceState:
    try:
        reviews = latest_source_rights_reviews(project)
    except (OSError, ValueError, ValidationError):
        reviews = {}
    return SourceWorkspaceState(
        recording_sha256=manifest.source_sha256,
        recording_reviewed=manifest.source_sha256.lower() in reviews,
        score_filename=score.source_filename if score is not None else None,
        score_format=score.source_format if score is not None else None,
        score_sha256=score.source_sha256 if score is not None else None,
        score_track_count=len(score.tracks) if score is not None else 0,
        score_reviewed=(score.source_sha256.lower() in reviews) if score is not None else False,
    )


def _workflow_has_required_work(plan) -> bool:
    """Return whether the workflow still has a required unfinished step.

    Optional steps are terminal by definition. A ready human-review step is also not an
    independently persistable workflow completion state: current package-eligible
    validation plus current exports are the concrete evidence that review did not block
    export. Automatic ready steps and every blocked step remain unfinished work.
    """

    return any(
        step.status == "blocked"
        or (step.status == "ready" and step.mode == "automatic")
        for step in plan.steps
    )


def build_song_workspace_snapshot(project_dir: Path) -> SongWorkspaceSnapshot:
    project = project_dir.expanduser().resolve()
    manifest = ProjectManifest.load(project)
    plan = build_multi_arrangement_workflow_plan(project)
    score = _score_or_none(project)

    review_queue: list[WorkspaceReviewItem] = []
    arrangements: list[ArrangementWorkspaceState] = []
    any_validation_fail = False
    any_validation_problem = False
    configured_roles = {value.lower() for value in manifest.arrangement_instruments}

    for role in (ArrangementRole.bass, ArrangementRole.lead, ArrangementRole.rhythm):
        validation_path = _validation_path(project, role)
        report, validation_problem = _read_validation(validation_path)
        validation_state: ValidationState
        if validation_problem is not None:
            validation_state = "INVALID"
            any_validation_problem = any_validation_problem or role.value in configured_roles
            review_queue.append(
                WorkspaceReviewItem(
                    arrangement=role.value,
                    code="invalid_validation_report",
                    severity="FAIL",
                    stage="validation",
                    message=validation_problem,
                    priority=100,
                )
            )
        else:
            validation_state = report.status if report is not None else "NOT_RUN"

        if report is not None:
            any_validation_fail = any_validation_fail or report.status == "FAIL"
            for item in report.review_queue:
                review_queue.append(
                    WorkspaceReviewItem(
                        arrangement=role.value,
                        code=item.code,
                        severity=item.severity,
                        stage=item.stage,
                        message=item.message,
                        time_seconds=item.time_seconds,
                        note_index=item.note_index,
                        priority=item.priority,
                    )
                )
        mapping = score.mapping_for(role) if score is not None else None
        draft_state = _draft_state(project, role)
        export_xml_ready = bool(
            draft_state == "CURRENT"
            and report is not None
            and validation_problem is None
            and report.can_package
            and _export_path(project, role).is_file()
        )
        arrangements.append(
            ArrangementWorkspaceState(
                role=role.value,
                configured=role.value in configured_roles,
                score_track_index=mapping.source_track_index if mapping is not None else None,
                mapping_confirmed=bool(mapping is not None and mapping.human_confirmed),
                draft_state=draft_state,
                validation_state=validation_state,
                validation_problem=validation_problem,
                fail_count=report.fail_count if report is not None else 0,
                warning_count=report.warning_count if report is not None else 0,
                export_xml_ready=export_xml_ready,
            )
        )

    review_queue.sort(
        key=lambda item: (
            -item.priority,
            item.time_seconds if item.time_seconds is not None else -1.0,
            item.arrangement,
            item.stage,
            item.code,
        )
    )

    total_steps = len(plan.steps)
    complete_steps = sum(step.status == "complete" for step in plan.steps)
    progress = round((complete_steps / total_steps) * 100) if total_steps else 0
    next_step = next((step for step in plan.steps if step.step_id == plan.next_step_id), None)

    configured_arrangements = [item for item in arrangements if item.configured]
    all_exports_ready = bool(configured_arrangements) and all(item.export_xml_ready for item in configured_arrangements)
    workflow_complete = bool(plan.steps) and not _workflow_has_required_work(plan)
    if any_validation_problem or any_validation_fail:
        health: WorkspaceHealth = "BLOCKED"
    elif plan.human_blocking_steps:
        health = "REVIEW"
    elif all_exports_ready and workflow_complete:
        health = "READY"
    elif complete_steps == 0:
        health = "NEW"
    else:
        health = "IN_PROGRESS"

    return SongWorkspaceSnapshot(
        project_path=str(project),
        project_name=manifest.project_name,
        artist=manifest.artist,
        title=manifest.title,
        duration_seconds=manifest.source_metadata.duration_seconds,
        health=health,
        progress_percent=progress,
        complete_steps=complete_steps,
        total_steps=total_steps,
        automatic_ready_steps=plan.automatic_ready_steps,
        human_blocking_steps=plan.human_blocking_steps,
        next_step_id=plan.next_step_id,
        next_action_title=next_step.title if next_step is not None else None,
        next_action_reason=next_step.reason if next_step is not None else None,
        sources=_source_snapshot(project, manifest, score),
        timeline=_timeline_snapshot(project, manifest.source_metadata.duration_seconds),
        arrangements=arrangements,
        review_queue=review_queue,
    )
