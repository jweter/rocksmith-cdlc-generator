from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from .guitarpro_import import import_project_guitarpro
from .hashing import sha256_file
from .midi_import import import_project_midi
from .models import ProjectManifest
from .musicxml_import import import_project_musicxml
from .project import create_project
from .psarc_import import import_project_psarc
from .source_import import ImportedSource
from .source_intake import SourceIntakeDescriptor, SourceRightsClass
from .source_router import SourceRoute, route_local_source


class SourceIntakeReceipt(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    descriptor: SourceIntakeDescriptor
    route_action: str
    route_reason: str
    source_sha256: str
    output_relative_path: str | None = None


class AddSourceResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: Literal["complete", "queued"]
    route: SourceRoute
    output_path: str | None = None
    intake_receipt_path: str | None = None
    human_rights_review_required: bool


def _require_project(project: Path) -> Path:
    resolved = project.expanduser().resolve()
    if not (resolved / "project.json").is_file():
        raise FileNotFoundError(f"Not a CDLC project: {resolved}")
    return resolved


def _receipt_stem(source: Path) -> str:
    """Return a bounded ASCII receipt stem safe for common filesystem limits."""
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", source.stem).strip("-._")
    return (normalized or "source")[:96]


def _write_intake_receipt(
    project: Path,
    *,
    source: Path,
    route: SourceRoute,
    source_sha256: str,
    output: Path | None,
) -> Path:
    relative_output: str | None = None
    if output is not None:
        try:
            relative_output = str(output.resolve().relative_to(project.resolve()))
        except ValueError:
            relative_output = None

    receipt = SourceIntakeReceipt(
        descriptor=route.descriptor,
        route_action=route.action,
        route_reason=route.reason,
        source_sha256=source_sha256,
        output_relative_path=relative_output,
    )
    destination = (
        project
        / "sources"
        / "intake"
        / f"{_receipt_stem(source)}-{source_sha256[:12]}.json"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(receipt.model_dump_json(indent=2), encoding="utf-8")
    return destination


def _completed_ingest_sha256(
    *,
    route: SourceRoute,
    project: Path,
    output: Path,
) -> str:
    """Read the source hash recorded by the workflow that actually completed."""
    if route.action == "project_audio":
        return ProjectManifest.load(project).source_sha256
    return ImportedSource.read_json(output).provenance.source_sha256


def add_local_source(
    source: Path,
    *,
    project: Path | None = None,
    title: str | None = None,
    artist: str | None = None,
    instruments: list[str] | None = None,
    projects_root: Path = Path("projects"),
    rights_class: SourceRightsClass = SourceRightsClass.unknown,
    license_note: str | None = None,
    instrument: Literal["bass", "lead", "rhythm"] = "bass",
    track_index: int | None = None,
    part_index: int | None = None,
    bridge_path: Path | None = None,
) -> AddSourceResult:
    """Route and execute one explicitly supplied local source.

    This is deliberately local-only. Streaming/video references belong to the
    reference-discovery path and are never converted into ingest bytes here.
    """

    source = source.expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    if rights_class is SourceRightsClass.streaming_reference_only:
        raise ValueError("streaming-reference-only material cannot be added as local source bytes")

    route = route_local_source(
        source,
        rights_class=rights_class,
        license_note=license_note,
    )
    review_required = route.descriptor.requires_human_rights_review

    if route.action == "reject_unknown":
        raise ValueError(route.reason)

    source_sha = sha256_file(source)

    if route.action == "queue_adapter":
        receipt_path: Path | None = None
        if project is not None:
            resolved_project = _require_project(project)
            receipt_path = _write_intake_receipt(
                resolved_project,
                source=source,
                route=route,
                source_sha256=source_sha,
                output=None,
            )
        return AddSourceResult(
            status="queued",
            route=route,
            intake_receipt_path=str(receipt_path) if receipt_path is not None else None,
            human_rights_review_required=review_required,
        )

    if route.action == "project_audio":
        if project is not None:
            raise ValueError("audio project creation does not accept --project; omit it for a new project")
        if title is None or not title.strip():
            raise ValueError("recognized audio requires --title so a new project can be created")
        output = create_project(
            audio=source,
            projects_root=projects_root,
            artist=artist,
            title=title.strip(),
            instruments=instruments or ["bass"],
        )
        project_dir = Path(output).resolve()
    else:
        if project is None:
            raise ValueError(f"{route.descriptor.source_format.value} import requires --project")
        project_dir = _require_project(project)
        if route.action == "import_midi":
            output = import_project_midi(
                project_dir,
                source,
                track_index=track_index,
                instrument=instrument,
            )
        elif route.action == "import_guitarpro":
            output = import_project_guitarpro(
                project_dir,
                source,
                track_index=track_index,
                instrument=instrument,
            )
        elif route.action == "import_musicxml":
            output = import_project_musicxml(
                project_dir,
                source,
                part_index=part_index,
                instrument=instrument,
            )
        elif route.action == "import_psarc":
            if instrument != "bass":
                raise ValueError("current PSARC bridge imports Bass arrangements only")
            output = import_project_psarc(project_dir, source, bridge_path=bridge_path)
        else:  # pragma: no cover - SourceRoute constrains executable actions.
            raise ValueError(f"No executor registered for route {route.action}")

    output_path = Path(output).resolve()
    completed_sha = _completed_ingest_sha256(
        route=route,
        project=project_dir,
        output=output_path,
    )
    if sha256_file(source) != completed_sha:
        raise IOError("Source bytes changed during ingest; refusing to write a mismatched intake receipt")

    receipt_path = _write_intake_receipt(
        project_dir,
        source=source,
        route=route,
        source_sha256=completed_sha,
        output=output_path,
    )

    return AddSourceResult(
        status="complete",
        route=route,
        output_path=str(output_path),
        intake_receipt_path=str(receipt_path),
        human_rights_review_required=review_required,
    )
