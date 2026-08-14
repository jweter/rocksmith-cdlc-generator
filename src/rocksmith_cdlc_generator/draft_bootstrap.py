from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from .project_score import RegisteredProjectScore, register_project_score
from .source_intake import SourceRightsClass
from .source_workflow import AddSourceResult, add_local_source
from .workflow_runner import AutomaticWorkflowRun, run_automatic_first_draft

_SHARED_SCORE_SUFFIXES = {".gp3", ".gp4", ".gp5", ".xml", ".musicxml", ".mxl"}


class DraftBootstrapResult(BaseModel):
    """Structured result for creating a Bass project and advancing its safe first draft."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    project_path: str
    title: str
    artist: str | None = None
    audio_intake_receipt: str | None = None
    notation_intake_receipt: str | None = None
    score_source_path: str | None = None
    automatic_run: AutomaticWorkflowRun


class DraftBootstrapError(RuntimeError):
    """Failure that preserves which bootstrap stage failed and any project already created."""

    def __init__(self, stage: str, message: str, *, project_path: str | None = None) -> None:
        super().__init__(message)
        self.stage = stage
        self.project_path = project_path


def _require_completed_project(result: AddSourceResult) -> Path:
    if result.status != "complete" or result.output_path is None:
        raise DraftBootstrapError(
            "audio_intake",
            "Recording audio did not create a complete project.",
        )
    project = Path(result.output_path).expanduser().resolve()
    if not (project / "project.json").is_file():
        raise DraftBootstrapError(
            "audio_intake",
            f"Audio intake reported a project that is missing project.json: {project}",
        )
    return project


def create_and_run_first_draft(
    audio: Path,
    *,
    title: str | None = None,
    artist: str | None = None,
    notation: Path | None = None,
    projects_root: Path = Path("projects"),
    audio_rights_class: SourceRightsClass = SourceRightsClass.unknown,
    audio_license_note: str | None = None,
    notation_rights_class: SourceRightsClass = SourceRightsClass.unknown,
    notation_license_note: str | None = None,
    track_index: int | None = None,
    part_index: int | None = None,
    bridge_path: Path | None = None,
    max_steps: int = 8,
) -> DraftBootstrapResult:
    """Create a Bass project from local audio, optionally import notation, then auto-advance.

    Complete Guitar Pro 3-5 and MusicXML/MXL notation is first registered once as a
    project-level shared score. Its Bass/Lead/Rhythm mappings remain proposals only.
    The existing Bass extraction then runs as a compatibility path until confirmed
    shared-score mappings can fan out into all three arrangement pipelines.

    Rights/source acceptance is never inferred. With the default ``unknown`` rights
    classification, the automatic runner stops at the existing human provenance gate.
    Supplying an explicit reviewed local-use rights class merely records that user's
    assertion; it does not elevate musical truth or redistribution permission.
    """

    audio = audio.expanduser().resolve()
    resolved_title = title.strip() if title and title.strip() else audio.stem
    if not resolved_title:
        raise DraftBootstrapError("audio_intake", "A non-empty song title is required.")

    try:
        audio_result = add_local_source(
            audio,
            title=resolved_title,
            artist=artist,
            instruments=["bass"],
            projects_root=projects_root,
            rights_class=audio_rights_class,
            license_note=audio_license_note,
            instrument="bass",
        )
    except Exception as exc:
        raise DraftBootstrapError("audio_intake", str(exc)) from exc

    project = _require_completed_project(audio_result)
    notation_result: AddSourceResult | None = None
    score_registration: RegisteredProjectScore | None = None

    if notation is not None:
        resolved_notation = notation.expanduser().resolve()
        if resolved_notation.suffix.lower() in _SHARED_SCORE_SUFFIXES:
            try:
                score_registration = register_project_score(
                    project,
                    resolved_notation,
                    rights_class=notation_rights_class,
                    license_note=notation_license_note,
                )
            except Exception as exc:
                raise DraftBootstrapError(
                    "score_registration",
                    str(exc),
                    project_path=str(project),
                ) from exc

        try:
            notation_result = add_local_source(
                resolved_notation,
                project=project,
                rights_class=notation_rights_class,
                license_note=notation_license_note,
                instrument="bass",
                track_index=track_index,
                part_index=part_index,
                bridge_path=bridge_path,
            )
        except Exception as exc:
            raise DraftBootstrapError(
                "notation_intake",
                str(exc),
                project_path=str(project),
            ) from exc

    try:
        automatic_run = run_automatic_first_draft(project, max_steps=max_steps)
    except Exception as exc:
        raise DraftBootstrapError(
            "automatic_run",
            str(exc),
            project_path=str(project),
        ) from exc

    return DraftBootstrapResult(
        project_path=str(project),
        title=resolved_title,
        artist=artist.strip() if artist and artist.strip() else None,
        audio_intake_receipt=audio_result.intake_receipt_path,
        notation_intake_receipt=(
            notation_result.intake_receipt_path if notation_result is not None else None
        ),
        score_source_path=(
            score_registration.score_source_path if score_registration is not None else None
        ),
        automatic_run=automatic_run,
    )
