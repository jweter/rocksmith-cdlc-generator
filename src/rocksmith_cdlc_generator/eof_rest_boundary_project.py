from __future__ import annotations

from pathlib import Path

from .eof_bridge import resolve_registered_score_for_eof
from .eof_rest_boundary_check import EOFRestBoundaryReport, analyze_guitarpro_rest_boundaries
from .guitarpro_import import ArrangementKind

EOF_REST_BOUNDARY_REPORT_PATH = Path("review") / "eof_rest_boundary_report.json"


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


def build_project_eof_rest_boundary_report(
    project_dir: Path,
    *,
    instrument: ArrangementKind = "bass",
    track_index: int | None = None,
    overlap_tolerance_seconds: float = 1e-6,
) -> EOFRestBoundaryReport:
    """Compare the project's registered GP score against EOF-derived explicit rest boundaries.

    The current immutable registered score is reparsed at the resolved arrangement track index.
    The result is evidence-only: it does not change notes, timing, review state, validation
    state, or package readiness. See ``eof_rest_boundary_check`` for the ported EOF invariant
    this reuses (``raynebc/editor-on-fire``, audited at the commit recorded there).
    """

    project = _project(project_dir)
    score_path = resolve_registered_score_for_eof(project)
    return analyze_guitarpro_rest_boundaries(
        score_path,
        instrument=instrument,
        track_index=track_index,
        overlap_tolerance_seconds=overlap_tolerance_seconds,
    )


def write_project_eof_rest_boundary_report(
    project_dir: Path,
    *,
    instrument: ArrangementKind = "bass",
    track_index: int | None = None,
    overlap_tolerance_seconds: float = 1e-6,
) -> tuple[Path, EOFRestBoundaryReport]:
    """Persist the latest advisory rest-boundary comparison under the project review dir."""

    project = _project(project_dir)
    report = build_project_eof_rest_boundary_report(
        project,
        instrument=instrument,
        track_index=track_index,
        overlap_tolerance_seconds=overlap_tolerance_seconds,
    )
    destination = project / EOF_REST_BOUNDARY_REPORT_PATH
    _atomic_write(destination, report.model_dump_json(indent=2) + "\n")
    return destination, report
