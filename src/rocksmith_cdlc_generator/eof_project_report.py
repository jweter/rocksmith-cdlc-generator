from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .eof_bridge import resolve_registered_score_for_eof
from .eof_compatibility import (
    EOFCompatibilityFixture,
    EOFCompatibilityReport,
    compare_imported_source_to_eof_fixture,
)
from .guitarpro_import import (
    GUITARPRO_ADAPTER_ID,
    ArrangementKind,
    guitarpro_adapter_sha256,
    guitarpro_runtime_version,
    import_guitarpro,
)

EOF_PROJECT_REPORT_PATH = Path("review") / "eof_compatibility_report.json"


class EOFProjectCompatibilityReport(BaseModel):
    """Project-local derivative report; EOF evidence never becomes chart authority."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[2] = 2
    instrument: ArrangementKind
    score_relative_path: str
    fixture_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    eof_version: str
    evidence_note: str
    importer: Literal["pyguitarpro-adapter"]
    importer_version: str = Field(min_length=1)
    adapter_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    comparison: EOFCompatibilityReport

    @property
    def matched(self) -> bool:
        return self.comparison.matched


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


def build_project_eof_compatibility_report(
    project_dir: Path,
    fixture_path: Path,
    *,
    instrument: ArrangementKind,
    timing_tolerance_seconds: float = 1e-6,
) -> EOFProjectCompatibilityReport:
    """Compare the current registered GP score with source-bound EOF observations.

    The current immutable registered score is reparsed through the real Guitar Pro
    importer at the fixture's exact source-track index. The result is evidence-only:
    it does not change mappings, notes, timing, positions, techniques, review state,
    validation state, or package readiness.
    """

    project = _project(project_dir)
    resolved_fixture_path = fixture_path.expanduser().resolve()
    fixture_bytes = resolved_fixture_path.read_bytes()
    fixture = EOFCompatibilityFixture.model_validate_json(fixture_bytes)
    score_path = resolve_registered_score_for_eof(project)
    imported = import_guitarpro(
        score_path,
        track_index=fixture.source_track_index,
        instrument=instrument,
    )
    comparison = compare_imported_source_to_eof_fixture(
        imported,
        fixture,
        timing_tolerance_seconds=timing_tolerance_seconds,
    )
    return EOFProjectCompatibilityReport(
        instrument=instrument,
        score_relative_path=score_path.relative_to(project).as_posix(),
        fixture_sha256=hashlib.sha256(fixture_bytes).hexdigest(),
        eof_version=fixture.eof_version,
        evidence_note=fixture.evidence_note,
        importer=GUITARPRO_ADAPTER_ID,
        importer_version=imported.provenance.importer_version,
        adapter_sha256=guitarpro_adapter_sha256(),
        comparison=comparison,
    )


def load_current_project_eof_compatibility_report(
    project_dir: Path,
) -> EOFProjectCompatibilityReport | None:
    """Load the latest advisory report only when it still matches the registered score.

    A report is derivative evidence, not authority. Score-path or content drift makes it
    stale and therefore unsuitable for normal-path display as a current observation.
    """

    project = _project(project_dir)
    destination = project / EOF_PROJECT_REPORT_PATH
    if not destination.is_file():
        return None

    report = EOFProjectCompatibilityReport.model_validate_json(
        destination.read_text(encoding="utf-8")
    )
    score_path = resolve_registered_score_for_eof(project)
    expected_relative = score_path.relative_to(project).as_posix()
    if report.score_relative_path != expected_relative:
        raise ValueError("EOF compatibility report is stale for the registered score path")

    score_sha256 = hashlib.sha256(score_path.read_bytes()).hexdigest()
    if report.comparison.score_sha256 != score_sha256:
        raise ValueError("EOF compatibility report is stale for the registered score content")
    if report.importer_version != guitarpro_runtime_version():
        raise ValueError("EOF compatibility report is stale for the Guitar Pro runtime")
    if report.adapter_sha256 != guitarpro_adapter_sha256():
        raise ValueError("EOF compatibility report is stale for the Guitar Pro adapter")
    return report


def write_project_eof_compatibility_report(
    project_dir: Path,
    fixture_path: Path,
    *,
    instrument: ArrangementKind,
    timing_tolerance_seconds: float = 1e-6,
) -> tuple[Path, EOFProjectCompatibilityReport]:
    """Persist the latest advisory comparison under the project review directory."""

    project = _project(project_dir)
    report = build_project_eof_compatibility_report(
        project,
        fixture_path,
        instrument=instrument,
        timing_tolerance_seconds=timing_tolerance_seconds,
    )
    destination = project / EOF_PROJECT_REPORT_PATH
    _atomic_write(destination, report.model_dump_json(indent=2) + "\n")
    return destination, report
