from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from .metadata_providers import SelectedMetadata
from .reference_selection import ReferenceSelection, load_reference_selection


class ReviewedRecordingContext(BaseModel):
    """Machine-readable handoff for explicitly reviewed recording/version identity.

    This artifact is metadata-only. It snapshots human-confirmed reference evidence
    and, when present, the separately selected catalog metadata candidate. It does
    not authorize downloading, ingestion, benchmark use, or redistribution.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: int = 1
    reference_selection: ReferenceSelection
    selected_metadata: SelectedMetadata | None = None
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


def _context_path(project_dir: Path) -> Path:
    return project_dir / "metadata" / "recording_context.json"


def _selected_metadata_path(project_dir: Path) -> Path:
    return project_dir / "metadata" / "selected.json"


def build_reviewed_recording_context(project_dir: Path) -> Path:
    """Persist the current reviewed reference plus optional selected catalog metadata."""

    project_dir = project_dir.expanduser().resolve()
    if not (project_dir / "project.json").is_file():
        raise FileNotFoundError(f"Not a CDLC project: {project_dir}")

    reference = load_reference_selection(project_dir)
    if reference is None:
        raise ValueError("a human-confirmed reference selection is required before building recording context")

    selected_path = _selected_metadata_path(project_dir)
    selected_metadata = None
    if selected_path.is_file():
        selected_metadata = SelectedMetadata.model_validate_json(
            selected_path.read_text(encoding="utf-8")
        )

    context = ReviewedRecordingContext(
        reference_selection=reference,
        selected_metadata=selected_metadata,
    )
    output = _context_path(project_dir)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(context.model_dump_json(indent=2), encoding="utf-8")
    return output


def load_reviewed_recording_context(project_dir: Path) -> ReviewedRecordingContext | None:
    path = _context_path(project_dir.expanduser().resolve())
    if not path.is_file():
        return None
    return ReviewedRecordingContext.model_validate_json(path.read_text(encoding="utf-8"))
