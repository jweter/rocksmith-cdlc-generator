from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from .hashing import sha256_file
from .score_inventory import inventory_score
from .score_source import ProjectScoreSource
from .source_intake import SourceRightsClass
from .source_router import route_local_source
from .source_workflow import SourceIntakeReceipt

_SUPPORTED_SUFFIXES = {".gp3", ".gp4", ".gp5", ".xml", ".musicxml", ".mxl"}


class RegisteredProjectScore(BaseModel):
    """Result of registering one complete symbolic score under a CDLC project."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    project_path: str
    stored_source_path: str
    score_source_path: str
    intake_receipt_path: str
    human_rights_review_required: bool


def _require_project(project: Path) -> Path:
    resolved = project.expanduser().resolve()
    if not (resolved / "project.json").is_file():
        raise FileNotFoundError(f"Not a CDLC project: {resolved}")
    return resolved


def _bounded_stem(source: Path) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", source.stem).strip("-._")
    return (normalized or "score")[:80]


def _write_registration_receipt(
    project: Path,
    *,
    source: Path,
    source_sha256: str,
    output: Path,
    rights_class: SourceRightsClass,
    license_note: str | None,
) -> Path:
    route = route_local_source(source, rights_class=rights_class, license_note=license_note)
    receipt = SourceIntakeReceipt(
        descriptor=route.descriptor,
        route_action="register_score_source",
        route_reason="Registered complete symbolic score without accepting an arrangement mapping.",
        source_sha256=source_sha256,
        output_relative_path=str(output.relative_to(project)),
    )
    destination = (
        project
        / "sources"
        / "intake"
        / f"{_bounded_stem(source)}-{source_sha256[:12]}-score.json"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(receipt.model_dump_json(indent=2), encoding="utf-8")
    return destination


def register_project_score(
    project: Path,
    source: Path,
    *,
    rights_class: SourceRightsClass = SourceRightsClass.unknown,
    license_note: str | None = None,
) -> RegisteredProjectScore:
    """Persist one complete local score plus inventory without accepting role mappings.

    Registration is local-only and immutable-by-hash. It records the user's rights
    classification but does not elevate provenance, musical correctness, or any
    proposed Bass/Lead/Rhythm mapping to human-confirmed state.
    """

    project = _require_project(project)
    source = source.expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    if source.suffix.lower() not in _SUPPORTED_SUFFIXES:
        raise ValueError("Project score registration supports MusicXML/MXL and Guitar Pro 3-5")
    if rights_class is SourceRightsClass.streaming_reference_only:
        raise ValueError("streaming-reference-only material cannot be registered as local score bytes")

    route = route_local_source(source, rights_class=rights_class, license_note=license_note)
    if route.action not in {"import_guitarpro", "import_musicxml"}:
        raise ValueError(f"Unsupported score registration route: {route.action}")

    source_sha = sha256_file(source)
    score_root = project / "sources" / "score"
    source_dir = score_root / "original"
    source_dir.mkdir(parents=True, exist_ok=True)
    stored = source_dir / f"{_bounded_stem(source)}-{source_sha[:12]}{source.suffix.lower()}"

    existing_contract_path = score_root / "source.json"
    if existing_contract_path.is_file():
        existing = ProjectScoreSource.read_json(existing_contract_path)
        if existing.source_sha256 != source_sha:
            raise ValueError(
                "Project already has a different registered score; explicit replacement is required"
            )

    if stored.is_file():
        if sha256_file(stored) != source_sha:
            raise IOError(f"Registered score destination hash mismatch: {stored}")
    else:
        shutil.copyfile(source, stored)

    if sha256_file(source) != source_sha or sha256_file(stored) != source_sha:
        if stored.is_file() and sha256_file(stored) != source_sha:
            stored.unlink(missing_ok=True)
        raise IOError("Source bytes changed during score registration")

    relative_stored = str(stored.relative_to(project))
    inventory = inventory_score(stored, imported_relative_path=relative_stored)
    if inventory.source_sha256 != source_sha:
        raise IOError("Score inventory hash does not match registered source bytes")
    inventory.write_json(existing_contract_path)

    receipt = _write_registration_receipt(
        project,
        source=source,
        source_sha256=source_sha,
        output=stored,
        rights_class=rights_class,
        license_note=license_note,
    )
    return RegisteredProjectScore(
        project_path=str(project),
        stored_source_path=str(stored),
        score_source_path=str(existing_contract_path),
        intake_receipt_path=str(receipt),
        human_rights_review_required=route.descriptor.requires_human_rights_review,
    )
