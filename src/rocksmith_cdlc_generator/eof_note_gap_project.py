from __future__ import annotations

from pathlib import Path

from .eof_note_gap_check import EOFNoteGapReport, compute_eof_note_gap_check
from .guitarpro_import import ArrangementKind
from .reviewed_export_events import reviewed_export_arrangement
from .score_source import ArrangementRole

EOF_NOTE_GAP_REPORT_PATH = Path("review") / "eof_note_gap_report.json"


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


def build_project_eof_note_gap_report(
    project_dir: Path,
    *,
    instrument: ArrangementKind = "bass",
    touch_tolerance_seconds: float = 1e-6,
) -> EOFNoteGapReport:
    """Compare the project's reviewed export arrangement against EOF's same-string sustain ceiling.

    Reuses this project's existing post-reconciliation/post-materialization read model
    (``reviewed_export_events.reviewed_export_arrangement``) rather than re-deriving it. The
    result is evidence-only: it does not change notes, timing, review state, validation state,
    or package readiness. See ``eof_note_gap_check`` for the ported EOF invariant this reuses
    (``raynebc/editor-on-fire``, audited at the commit recorded there).
    """

    project = _project(project_dir)
    role = ArrangementRole(instrument)
    arrangement = reviewed_export_arrangement(project, role)
    return compute_eof_note_gap_check(arrangement, touch_tolerance_seconds=touch_tolerance_seconds)


def write_project_eof_note_gap_report(
    project_dir: Path,
    *,
    instrument: ArrangementKind = "bass",
    touch_tolerance_seconds: float = 1e-6,
) -> tuple[Path, EOFNoteGapReport]:
    """Persist the latest advisory note-gap comparison under the project review dir."""

    project = _project(project_dir)
    report = build_project_eof_note_gap_report(
        project,
        instrument=instrument,
        touch_tolerance_seconds=touch_tolerance_seconds,
    )
    destination = project / EOF_NOTE_GAP_REPORT_PATH
    _atomic_write(destination, report.model_dump_json(indent=2) + "\n")
    return destination, report
