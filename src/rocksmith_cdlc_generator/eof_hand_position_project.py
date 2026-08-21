from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .eof_bridge import resolve_registered_score_for_eof
from .eof_hand_position_observation import (
    EOFHandPositionEvidenceStatus,
    EOFHandPositionFixture,
    validate_eof_hand_position_fixture,
)
from .guitarpro_import import (
    GUITARPRO_ADAPTER_ID,
    ArrangementKind,
    guitarpro_adapter_sha256,
    guitarpro_runtime_version,
    import_guitarpro,
)

EOF_HAND_POSITION_STATUS_PATH = Path("review") / "eof_hand_position_status.json"


class EOFProjectHandPositionStatus(BaseModel):
    """Project-local derivative status for advisory EOF hand-position evidence."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    instrument: ArrangementKind
    score_relative_path: str
    fixture_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    eof_version: str = Field(min_length=1)
    evidence_note: str = Field(min_length=1)
    importer: Literal["pyguitarpro-adapter"]
    importer_version: str = Field(min_length=1)
    adapter_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence: EOFHandPositionEvidenceStatus


def _project(project_dir: Path) -> Path:
    project = project_dir.expanduser().resolve()
    if not (project / "project.json").is_file():
        raise FileNotFoundError(f"Not a CDLC project: {project}")
    return project


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def build_project_eof_hand_position_status(
    project_dir: Path,
    fixture_path: Path,
    *,
    instrument: ArrangementKind,
) -> EOFProjectHandPositionStatus:
    """Validate manually reviewed EOF hand-position evidence against the current score.

    The immutable registered Guitar Pro score is reparsed at the fixture's exact source
    track. Validation establishes provenance and event identity only. It does not infer
    hand spans, compare preferred fingering, score candidates, accept playability, or
    mutate any chart/review authority.
    """

    project = _project(project_dir)
    fixture_bytes = fixture_path.expanduser().resolve().read_bytes()
    fixture = EOFHandPositionFixture.model_validate_json(fixture_bytes)
    score_path = resolve_registered_score_for_eof(project)
    imported = import_guitarpro(
        score_path,
        track_index=fixture.source_track_index,
        instrument=instrument,
    )
    evidence = validate_eof_hand_position_fixture(imported, fixture)
    return EOFProjectHandPositionStatus(
        instrument=instrument,
        score_relative_path=score_path.relative_to(project).as_posix(),
        fixture_sha256=hashlib.sha256(fixture_bytes).hexdigest(),
        eof_version=fixture.eof_version,
        evidence_note=fixture.evidence_note,
        importer=GUITARPRO_ADAPTER_ID,
        importer_version=imported.provenance.importer_version,
        adapter_sha256=guitarpro_adapter_sha256(),
        evidence=evidence,
    )


def write_project_eof_hand_position_status(
    project_dir: Path,
    fixture_path: Path,
    *,
    instrument: ArrangementKind,
) -> tuple[Path, EOFProjectHandPositionStatus]:
    """Persist the latest advisory EOF hand-position evidence status under review/."""

    project = _project(project_dir)
    status = build_project_eof_hand_position_status(
        project,
        fixture_path,
        instrument=instrument,
    )
    destination = project / EOF_HAND_POSITION_STATUS_PATH
    _atomic_write(destination, status.model_dump_json(indent=2) + "\n")
    return destination, status


def load_current_project_eof_hand_position_status(
    project_dir: Path,
) -> EOFProjectHandPositionStatus | None:
    """Load persisted EOF hand-position evidence only while its derivation is current."""

    project = _project(project_dir)
    destination = project / EOF_HAND_POSITION_STATUS_PATH
    if not destination.is_file():
        return None

    status = EOFProjectHandPositionStatus.model_validate_json(
        destination.read_text(encoding="utf-8")
    )
    score_path = resolve_registered_score_for_eof(project)
    if status.score_relative_path != score_path.relative_to(project).as_posix():
        raise ValueError("EOF hand-position status is stale for the registered score path")
    if status.evidence.score_sha256 != hashlib.sha256(score_path.read_bytes()).hexdigest():
        raise ValueError("EOF hand-position status is stale for the registered score content")
    if status.importer_version != guitarpro_runtime_version():
        raise ValueError("EOF hand-position status is stale for the Guitar Pro runtime")
    if status.adapter_sha256 != guitarpro_adapter_sha256():
        raise ValueError("EOF hand-position status is stale for the Guitar Pro adapter")
    return status
