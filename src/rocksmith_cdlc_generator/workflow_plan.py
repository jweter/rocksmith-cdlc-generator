from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from .alignment import AlignmentReport
from .project_source_inventory import build_project_source_inventory
from .source_import import ImportedSource


StepStatus = Literal["complete", "ready", "blocked", "optional"]
StepMode = Literal["automatic", "human"]


class WorkflowStep(BaseModel):
    model_config = ConfigDict(frozen=True)

    step_id: str
    title: str
    status: StepStatus
    mode: StepMode
    command: str | None = None
    reason: str


class ProjectWorkflowPlan(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    project_path: str
    steps: list[WorkflowStep]
    next_step_id: str | None
    automatic_ready_steps: int
    human_blocking_steps: int


@dataclass(frozen=True)
class _ImportedBassSource:
    relative_path: str
    absolute_path: Path
    source: ImportedSource
    bass_track_indices: tuple[int, ...]


def _artifact(project: Path, relative: str) -> bool:
    return (project / relative).is_file()


def _safe_project_artifact(project: Path, relative: str) -> Path | None:
    candidate = (project / relative).resolve()
    try:
        candidate.relative_to(project.resolve())
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


def _imported_bass_sources(project: Path, inventory) -> list[_ImportedBassSource]:
    sources: list[_ImportedBassSource] = []
    seen: set[Path] = set()
    for item in inventory.local_sources:
        if item.family not in {"notation", "rocksmith_package"}:
            continue
        if item.parser_pending or item.output_relative_path is None:
            continue
        path = _safe_project_artifact(project, item.output_relative_path)
        if path is None or path.suffix.lower() != ".json" or path in seen:
            continue
        try:
            imported = ImportedSource.read_json(path)
        except (OSError, ValueError, ValidationError):
            continue
        bass_tracks = tuple(
            track.source_track_index
            for track in imported.tracks
            if track.instrument.strip().lower() == "bass"
        )
        if not bass_tracks:
            continue
        seen.add(path)
        sources.append(
            _ImportedBassSource(
                relative_path=str(path.relative_to(project.resolve())),
                absolute_path=path,
                source=imported,
                bass_track_indices=bass_tracks,
            )
        )
    return sorted(sources, key=lambda source: source.relative_path)


def _current_bass_alignment(project: Path, imported: list[_ImportedBassSource]) -> tuple[_ImportedBassSource, AlignmentReport] | None:
    alignment_path = project / "analysis" / "alignment.json"
    if not alignment_path.is_file():
        return None
    try:
        report = AlignmentReport.model_validate_json(alignment_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, ValidationError):
        return None

    report_path = Path(report.source_path).expanduser().resolve()
    for candidate in imported:
        if report_path != candidate.absolute_path:
            continue
        if report.source_sha256 != candidate.source.provenance.source_sha256:
            continue
        if report.track_index not in candidate.bass_track_indices:
            continue
        return candidate, report
    return None


def _align_command(project_q: str, source: _ImportedBassSource) -> str:
    source_q = f'"{source.absolute_path}"'
    if len(source.bass_track_indices) == 1:
        return f"cdlc align-source {project_q} --source {source_q} --track-index {source.bass_track_indices[0]}"
    return f"cdlc align-source {project_q} --source {source_q}"


def _reconcile_command(project_q: str, source: _ImportedBassSource) -> str:
    return f'cdlc reconcile-bass {project_q} --source "{source.absolute_path}"'


def build_project_workflow_plan(project_dir: Path) -> ProjectWorkflowPlan:
    """Describe the safest ordered path from current project state to a Bass first draft.

    This function is intentionally read-only. Automatic steps describe commands that can
    be run without making a human musical/source-acceptance decision; human steps remain
    explicit blockers rather than being silently approved.
    """

    inventory = build_project_source_inventory(project_dir)
    project = Path(inventory.project_path)
    project_q = f'"{project}"'
    steps: list[WorkflowStep] = []

    if inventory.local_audio_sources == 0:
        steps.append(WorkflowStep(
            step_id="recording-audio",
            title="Add recording audio",
            status="blocked",
            mode="human",
            reason="A recording is required before timing analysis or transcription can produce a song-matched draft.",
        ))
    else:
        steps.append(WorkflowStep(
            step_id="recording-audio",
            title="Recording audio available",
            status="complete",
            mode="human",
            reason="The project has local recording audio.",
        ))

    if inventory.unresolved_rights_reviews:
        steps.append(WorkflowStep(
            step_id="source-rights",
            title="Confirm local-source rights/provenance",
            status="blocked",
            mode="human",
            reason=f"{inventory.unresolved_rights_reviews} local source(s) still require explicit provenance review.",
        ))
    else:
        steps.append(WorkflowStep(
            step_id="source-rights",
            title="Local-source rights/provenance reviewed",
            status="complete",
            mode="human",
            reason="No unresolved local-source rights reviews remain.",
        ))

    if inventory.reference_count == 0:
        steps.append(WorkflowStep(
            step_id="recording-reference",
            title="Add/select recording-version reference",
            status="optional",
            mode="human",
            reason="A public reference is optional, but useful for distinguishing studio/live/remaster versions.",
        ))
    elif not inventory.selected_reference:
        steps.append(WorkflowStep(
            step_id="recording-reference",
            title="Select intended recording/version",
            status="blocked",
            mode="human",
            reason="Multiple or unselected references cannot be resolved safely without human confirmation.",
        ))
    elif not inventory.reviewed_recording_context:
        steps.append(WorkflowStep(
            step_id="recording-reference",
            title="Review recording context",
            status="blocked",
            mode="human",
            command=f"cdlc-reference context {project_q}",
            reason="The selected reference must be explicitly reviewed before it becomes downstream recording identity.",
        ))
    else:
        steps.append(WorkflowStep(
            step_id="recording-reference",
            title="Recording/version identity reviewed",
            status="complete",
            mode="human",
            reason="The reviewed recording context matches the current explicit selection.",
        ))

    source_ready = inventory.local_audio_sources > 0 and inventory.unresolved_rights_reviews == 0
    normalized = _artifact(project, "audio/normalized.wav")
    steps.append(WorkflowStep(
        step_id="normalize",
        title="Normalize working audio",
        status="complete" if normalized else ("ready" if source_ready else "blocked"),
        mode="automatic",
        command=None if normalized else f"cdlc normalize {project_q}",
        reason="Normalized working audio exists." if normalized else "Deterministic working audio is required for downstream analysis.",
    ))

    tempo = _artifact(project, "analysis/tempo_map.json")
    steps.append(WorkflowStep(
        step_id="tempo",
        title="Analyze beats and variable tempo",
        status="complete" if tempo else ("ready" if normalized else "blocked"),
        mode="automatic",
        command=None if tempo else f"cdlc tempo {project_q} --engine librosa",
        reason="Tempo map exists." if tempo else "The song timeline must be mapped before tabs/notes can be aligned to the recording.",
    ))

    bass_raw = _artifact(project, "analysis/bass_raw.json")
    steps.append(WorkflowStep(
        step_id="transcribe-bass",
        title="Generate audio-derived Bass draft",
        status="complete" if bass_raw else ("ready" if tempo else "blocked"),
        mode="automatic",
        command=None if bass_raw else f"cdlc transcribe-bass {project_q} --engine librosa-pyin",
        reason="Audio-derived Bass transcription exists." if bass_raw else "Audio evidence provides a fallback draft and a comparison target for imported tabs.",
    ))

    imported = _imported_bass_sources(project, inventory)
    current_alignment = _current_bass_alignment(project, imported)
    aligned_source = current_alignment[0] if current_alignment is not None else None
    reconciled = _artifact(project, "charts/bass_reconciled.json")

    if aligned_source is not None:
        steps.append(WorkflowStep(
            step_id="align-tab",
            title="Align tab/notation to recording",
            status="complete",
            mode="automatic",
            reason="The current alignment identifies one existing imported Bass source and Bass track.",
        ))
        steps.append(WorkflowStep(
            step_id="reconcile-tab",
            title="Reconcile tab parts with audio evidence",
            status="complete" if reconciled else ("ready" if bass_raw else "blocked"),
            mode="automatic",
            command=None if reconciled else _reconcile_command(project_q, aligned_source),
            reason="Reconciled Bass chart exists." if reconciled else "The previously aligned source is the explicit source choice; compare it with audio evidence and surface disagreements.",
        ))
    elif len(imported) == 1:
        source = imported[0]
        steps.append(WorkflowStep(
            step_id="align-tab",
            title="Align tab/notation to recording",
            status="ready" if tempo else "blocked",
            mode="automatic" if len(source.bass_track_indices) == 1 else "human",
            command=_align_command(project_q, source) if tempo and len(source.bass_track_indices) == 1 else None,
            reason=(
                "Match the imported Bass track to the actual recording timeline instead of trusting score tempo blindly."
                if len(source.bass_track_indices) == 1
                else f"This source contains {len(source.bass_track_indices)} Bass tracks; choosing the intended Bass arrangement requires human confirmation."
            ),
        ))
        steps.append(WorkflowStep(
            step_id="reconcile-tab",
            title="Reconcile tab parts with audio evidence",
            status="blocked",
            mode="automatic",
            reason="Reconciliation waits until this Bass source has a validated alignment to the recording.",
        ))
    elif len(imported) > 1:
        steps.append(WorkflowStep(
            step_id="align-tab",
            title="Choose tab/notation source to align",
            status="blocked",
            mode="human",
            reason=f"{len(imported)} imported Bass sources are available; choosing which represents the intended arrangement is a human source-acceptance decision. Running `cdlc align-source` for the chosen Bass source records that decision for later planning.",
        ))
    else:
        steps.append(WorkflowStep(
            step_id="align-tab",
            title="Add tab/notation for higher-confidence matching",
            status="optional",
            mode="human",
            reason="No existing parsed Bass symbolic source is available; the project can continue with audio-only transcription.",
        ))

    mapped = _artifact(project, "charts/bass_mapped.json")
    mapping_input_ready = reconciled or bass_raw
    steps.append(WorkflowStep(
        step_id="map-bass",
        title="Map Bass notes to playable strings/frets",
        status="complete" if mapped else ("ready" if mapping_input_ready else "blocked"),
        mode="automatic",
        command=None if mapped else f"cdlc map-bass {project_q} --source auto --tuning \"E Standard\" --max-fret 24",
        reason="Playable Bass mapping exists." if mapped else "Convert pitch events into a physically playable first-draft arrangement while preserving credible imported fingering.",
    ))

    validation = _artifact(project, "review/validation_report.json")
    steps.append(WorkflowStep(
        step_id="validate",
        title="Run unified validation and build review queue",
        status="complete" if validation else ("ready" if mapped else "blocked"),
        mode="automatic",
        command=None if validation else f"cdlc validate {project_q}",
        reason="Validation/review report exists." if validation else "The first draft must expose timing, mapping, confidence, and source-disagreement problems before export.",
    ))

    steps.append(WorkflowStep(
        step_id="human-review",
        title="Review flagged timing, notes, fingering, and source disagreements",
        status="ready" if validation else "blocked",
        mode="human",
        reason="Generated uncertainty must remain visible and human-correctable; the future Song Workspace will make this the primary GUI review step.",
    ))

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
