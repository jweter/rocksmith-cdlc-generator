from __future__ import annotations

from pathlib import Path

from .eof_bridge import resolve_registered_score_for_eof
from .eof_repeat_unfolding import EOFRepeatUnfoldingReport, analyze_guitarpro_repeat_unfolding
from .guitarpro_import import ArrangementKind

EOF_REPEAT_UNFOLDING_REPORT_PATH = Path("review") / "eof_repeat_unfolding_report.json"


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


def build_project_eof_repeat_unfolding_report(
    project_dir: Path,
    *,
    instrument: ArrangementKind = "bass",
    track_index: int | None = None,
) -> EOFRepeatUnfoldingReport:
    """Compare the project's registered GP score's written measure order against EOF-derived
    repeat/alternate-ending unfolding.

    The current immutable registered score is reparsed at the resolved arrangement track index.
    The result is evidence-only: it does not change notes, timing, review state, validation
    state, or package readiness. See ``eof_repeat_unfolding`` for the ported EOF invariant this
    reuses (``raynebc/editor-on-fire``, audited at the commit recorded there).
    """

    project = _project(project_dir)
    score_path = resolve_registered_score_for_eof(project)
    return analyze_guitarpro_repeat_unfolding(
        score_path,
        instrument=instrument,
        track_index=track_index,
    )


def write_project_eof_repeat_unfolding_report(
    project_dir: Path,
    *,
    instrument: ArrangementKind = "bass",
    track_index: int | None = None,
) -> tuple[Path, EOFRepeatUnfoldingReport]:
    """Persist the latest advisory repeat-unfolding comparison under the project review dir."""

    project = _project(project_dir)
    report = build_project_eof_repeat_unfolding_report(
        project,
        instrument=instrument,
        track_index=track_index,
    )
    destination = project / EOF_REPEAT_UNFOLDING_REPORT_PATH
    _atomic_write(destination, report.model_dump_json(indent=2) + "\n")
    return destination, report
