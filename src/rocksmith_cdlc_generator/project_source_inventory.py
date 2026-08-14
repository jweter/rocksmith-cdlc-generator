from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from .recording_context import load_reviewed_recording_context
from .reference_selection import load_reference_selection
from .reference_sources import load_reference_sources
from .source_workflow import SourceIntakeReceipt


class SourceInventoryItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    receipt_path: str
    display_name: str
    source_format: str
    family: str
    route_action: str
    rights_class: str
    adapter_status: str
    source_sha256: str
    output_relative_path: str | None = None
    human_rights_review_required: bool
    parser_pending: bool


class ProjectSourceInventory(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    project_path: str
    local_sources: list[SourceInventoryItem]
    local_audio_sources: int
    local_symbolic_sources: int
    reference_count: int
    selected_reference: bool
    reviewed_recording_context: bool
    unresolved_rights_reviews: int
    queued_adapter_sources: int
    next_actions: list[str]


def _project(project_dir: Path) -> Path:
    project = project_dir.expanduser().resolve()
    if not (project / "project.json").is_file():
        raise FileNotFoundError(f"Not a CDLC project: {project}")
    return project


def _load_receipts(project: Path) -> list[SourceInventoryItem]:
    directory = project / "sources" / "intake"
    if not directory.is_dir():
        return []

    items: list[SourceInventoryItem] = []
    for path in sorted(directory.glob("*.json")):
        receipt = SourceIntakeReceipt.model_validate_json(path.read_text(encoding="utf-8"))
        descriptor = receipt.descriptor
        items.append(
            SourceInventoryItem(
                receipt_path=str(path.relative_to(project)),
                display_name=descriptor.display_name,
                source_format=descriptor.source_format.value,
                family=descriptor.family.value,
                route_action=receipt.route_action,
                rights_class=descriptor.rights_class.value,
                adapter_status=descriptor.adapter_status.value,
                source_sha256=receipt.source_sha256,
                output_relative_path=receipt.output_relative_path,
                human_rights_review_required=descriptor.requires_human_rights_review,
                parser_pending=receipt.route_action == "queue_adapter",
            )
        )
    return items


def build_project_source_inventory(project_dir: Path) -> ProjectSourceInventory:
    """Build a read-only source/provenance readiness view for one local project."""

    project = _project(project_dir)
    local_sources = _load_receipts(project)
    references = load_reference_sources(project)
    selected_reference = load_reference_selection(project) is not None
    reviewed_context = load_reviewed_recording_context(project) is not None

    audio_count = sum(item.family == "audio" for item in local_sources)
    symbolic_count = sum(item.family in {"notation", "rocksmith_package"} for item in local_sources)
    unresolved_rights = sum(item.human_rights_review_required for item in local_sources)
    queued = sum(item.parser_pending for item in local_sources)

    actions: list[str] = []
    if audio_count == 0:
        actions.append("Add local recording audio with `cdlc add-source` before audio analysis/alignment.")
    if symbolic_count == 0:
        actions.append("Optionally add MIDI/tab/notation with `cdlc add-source`; audio-only transcription remains available.")
    if unresolved_rights:
        actions.append(f"Review rights/provenance for {unresolved_rights} local source(s).")
    if queued:
        actions.append(f"{queued} recognized source(s) are waiting for parser adapters.")
    if not references:
        actions.append("Optionally add public reference URLs with `cdlc-reference add` for version identification.")
    elif not selected_reference:
        actions.append("Select the intended recording/version with `cdlc-reference select`.")
    elif not reviewed_context:
        actions.append("Build the reviewed recording context with `cdlc-reference context`.")
    if audio_count > 0 and unresolved_rights == 0 and queued == 0 and reviewed_context:
        actions.append("Recording intake and reviewed identity are ready for analysis/alignment workflow.")

    return ProjectSourceInventory(
        project_path=str(project),
        local_sources=local_sources,
        local_audio_sources=audio_count,
        local_symbolic_sources=symbolic_count,
        reference_count=len(references),
        selected_reference=selected_reference,
        reviewed_recording_context=reviewed_context,
        unresolved_rights_reviews=unresolved_rights,
        queued_adapter_sources=queued,
        next_actions=actions,
    )
