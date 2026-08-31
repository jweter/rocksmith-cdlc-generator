from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from .models import ProjectManifest
from .recording_context import load_reviewed_recording_context
from .reference_selection import ReferenceSelection, load_reference_selection
from .reference_sources import load_reference_sources
from .source_intake import SourceFormat, adapter_status, detect_source_format, source_family
from .source_rights_review import latest_source_rights_reviews
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
    rights_review_path: str | None = None
    rights_reviewed_at: str | None = None


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
                receipt_path=path.relative_to(project).as_posix(),
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


def _manifest_audio_item(project: Path, existing: list[SourceInventoryItem]) -> SourceInventoryItem | None:
    """Expose immutable project audio for projects created before intake receipts existed.

    A valid ProjectManifest is authoritative evidence that project creation already
    accepted and inspected recording audio. Older `cdlc new` projects may use an
    FFmpeg-supported extension that the later intake enum does not recognize, so
    the inventory must not reclassify that manifest-backed recording as unknown.
    """

    try:
        manifest = ProjectManifest.load(project)
    except (ValidationError, ValueError, TypeError):
        return None

    if any(
        item.family == "audio" and item.source_sha256 == manifest.source_sha256
        for item in existing
    ):
        return None

    source_format = detect_source_format(manifest.source_project_path)
    if source_format is SourceFormat.unknown:
        format_label = (
            manifest.source_metadata.format_name
            or Path(manifest.source_project_path).suffix.lower().lstrip(".")
            or "manifest_audio"
        )
        adapter_label = "supported"
    else:
        format_label = source_format.value
        adapter_label = adapter_status(source_format).value

    return SourceInventoryItem(
        receipt_path="project.json",
        display_name=Path(manifest.source_project_path).name,
        source_format=format_label,
        family="audio",
        route_action="project_audio",
        rights_class="unknown",
        adapter_status=adapter_label,
        source_sha256=manifest.source_sha256,
        output_relative_path=manifest.source_project_path,
        human_rights_review_required=True,
        parser_pending=False,
    )


def _apply_rights_reviews(project: Path, items: list[SourceInventoryItem]) -> list[SourceInventoryItem]:
    latest = latest_source_rights_reviews(project)
    reviewed: list[SourceInventoryItem] = []
    for item in items:
        match = latest.get(item.source_sha256.lower())
        if match is None:
            reviewed.append(item)
            continue
        path, review = match
        reviewed.append(
            item.model_copy(
                update={
                    "rights_class": review.rights_class.value,
                    "human_rights_review_required": False,
                    "rights_review_path": path.relative_to(project).as_posix(),
                    "rights_reviewed_at": review.reviewed_at.isoformat(),
                }
            )
        )
    return reviewed


def _consolidate_rights_state_by_content(
    items: list[SourceInventoryItem],
) -> list[SourceInventoryItem]:
    """Fail closed when duplicate receipts disagree about rights for the same bytes.

    Source hashes identify one immutable content snapshot even when that snapshot has
    multiple intake/registration receipts. Every receipt for a hash receives the same
    effective review state so workflow gates and downstream consumers cannot observe a
    resolved subset while another receipt is unresolved or carries a conflicting class.
    """

    grouped: dict[str, list[SourceInventoryItem]] = {}
    for item in items:
        grouped.setdefault(item.source_sha256.lower(), []).append(item)

    effective: dict[str, tuple[bool, str]] = {}
    for sha, group in grouped.items():
        any_pending = any(item.human_rights_review_required for item in group)
        resolved_classes = {
            item.rights_class for item in group if not item.human_rights_review_required
        }
        conflicting_resolved_classes = len(resolved_classes) > 1
        review_required = any_pending or conflicting_resolved_classes
        if review_required:
            rights_class = "unknown"
        elif resolved_classes:
            rights_class = next(iter(resolved_classes))
        else:
            rights_class = group[0].rights_class
        effective[sha] = (review_required, rights_class)

    return [
        item.model_copy(
            update={
                "human_rights_review_required": effective[item.source_sha256.lower()][0],
                "rights_class": effective[item.source_sha256.lower()][1],
            }
        )
        for item in items
    ]


def _context_matches_selection(
    selection: ReferenceSelection | None,
    context_selection: ReferenceSelection | None,
) -> bool:
    if selection is None or context_selection is None:
        return False
    return str(selection.reference_url) == str(context_selection.reference_url)


def build_project_source_inventory(project_dir: Path) -> ProjectSourceInventory:
    """Build a read-only source/provenance readiness view for one local project."""

    project = _project(project_dir)
    local_sources = _load_receipts(project)
    manifest_audio = _manifest_audio_item(project, local_sources)
    if manifest_audio is not None:
        local_sources.insert(0, manifest_audio)
    local_sources = _apply_rights_reviews(project, local_sources)
    local_sources = _consolidate_rights_state_by_content(local_sources)

    references = load_reference_sources(project)
    selection = load_reference_selection(project)
    context = load_reviewed_recording_context(project)
    selected_reference = selection is not None
    reviewed_context = context is not None and _context_matches_selection(
        selection,
        context.reference_selection,
    )

    audio_count = sum(item.family == "audio" for item in local_sources)
    symbolic_count = sum(item.family in {"notation", "rocksmith_package"} for item in local_sources)
    unresolved_rights = len(
        {
            item.source_sha256.lower()
            for item in local_sources
            if item.human_rights_review_required
        }
    )
    queued = sum(item.parser_pending for item in local_sources)

    actions: list[str] = []
    if audio_count == 0:
        actions.append("Add local recording audio with `cdlc add-source` before audio analysis/alignment.")
    if symbolic_count == 0:
        actions.append("Optionally add MIDI/tab/notation with `cdlc add-source`; audio-only transcription remains available.")
    if unresolved_rights:
        actions.append(
            f"Review rights/provenance for {unresolved_rights} local source(s) with `cdlc-source-rights`."
        )
    if queued:
        actions.append(f"{queued} recognized source(s) are waiting for parser adapters.")
    if not references:
        actions.append("Optionally add public reference URLs with `cdlc-reference add` for version identification.")
    elif not selected_reference:
        actions.append("Select the intended recording/version with `cdlc-reference select`.")
    elif not reviewed_context:
        actions.append("Build or rebuild the reviewed recording context with `cdlc-reference context`.")
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
