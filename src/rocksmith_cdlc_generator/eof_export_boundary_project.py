from __future__ import annotations

from pathlib import Path

from .eof_export_boundary_check import EOFExportBoundaryReport, analyze_reviewed_export_boundaries
from .score_source import ArrangementRole

EOF_EXPORT_BOUNDARY_REPORT_PATH = Path("review") / "eof_export_boundary_report.json"


def _project(project_dir: Path) -> Path:
    project = project_dir.expanduser().resolve()
    if not (project / "project.json").is_file():
        raise FileNotFoundError(f"Not a CDLC project: {project}")
    return project


def _role(instrument: str) -> ArrangementRole:
    try:
        return ArrangementRole(instrument)
    except ValueError as exc:
        raise ValueError(f"Unsupported arrangement role: {instrument}") from exc


def write_project_eof_export_boundary_report(
    project_dir: Path,
    *,
    instrument: str = "bass",
    overlap_tolerance_seconds: float = 1e-6,
) -> tuple[Path, EOFExportBoundaryReport]:
    """Write the advisory post-materialization EOF boundary report."""
    project = _project(project_dir)
    report = analyze_reviewed_export_boundaries(
        project,
        _role(instrument),
        overlap_tolerance_seconds=overlap_tolerance_seconds,
    )
    destination = project / EOF_EXPORT_BOUNDARY_REPORT_PATH
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.tmp")
    temporary.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    temporary.replace(destination)
    return destination, report
