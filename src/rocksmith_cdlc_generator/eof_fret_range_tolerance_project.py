from __future__ import annotations

from pathlib import Path

from .eof_bridge import resolve_registered_score_for_eof
from .eof_fret_range_tolerance_check import (
    DEFAULT_FRET_RANGE_TOLERANCE,
    EOFFretRangeToleranceReport,
    analyze_guitarpro_fret_range_tolerance,
)
from .guitarpro_import import ArrangementKind

EOF_FRET_RANGE_TOLERANCE_REPORT_PATH = Path("review") / "eof_fret_range_tolerance_report.json"


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


def build_project_eof_fret_range_tolerance_report(
    project_dir: Path,
    *,
    instrument: ArrangementKind = "bass",
    track_index: int | None = None,
    fret_range_tolerance: int = DEFAULT_FRET_RANGE_TOLERANCE,
) -> EOFFretRangeToleranceReport:
    """Compare the project's registered GP score against EOF's default FHP tolerance rule.

    The current immutable registered score is reparsed at the resolved arrangement track index.
    The result is evidence-only: it does not select, write, or rewrite any fret-hand-position,
    note, timing, review state, validation state, or package readiness. See
    ``eof_fret_range_tolerance_check`` for the ported EOF decision this reuses
    (``raynebc/editor-on-fire``, audited at the commit recorded there).
    """

    project = _project(project_dir)
    score_path = resolve_registered_score_for_eof(project)
    return analyze_guitarpro_fret_range_tolerance(
        score_path,
        instrument=instrument,
        track_index=track_index,
        fret_range_tolerance=fret_range_tolerance,
    )


def write_project_eof_fret_range_tolerance_report(
    project_dir: Path,
    *,
    instrument: ArrangementKind = "bass",
    track_index: int | None = None,
) -> tuple[Path, EOFFretRangeToleranceReport]:
    """Persist the latest advisory fret-hand-position tolerance comparison under review/."""

    project = _project(project_dir)
    report = build_project_eof_fret_range_tolerance_report(
        project,
        instrument=instrument,
        track_index=track_index,
    )
    destination = project / EOF_FRET_RANGE_TOLERANCE_REPORT_PATH
    _atomic_write(destination, report.model_dump_json(indent=2) + "\n")
    return destination, report
