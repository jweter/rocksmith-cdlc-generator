from __future__ import annotations

from pathlib import Path

from .eof_bridge import resolve_registered_score_for_eof
from .eof_short_note_truncation_check import (
    EOF_DEFAULT_TRUNCATE_SHORT_CHORDS,
    EOF_DEFAULT_TRUNCATE_SHORT_NOTES,
    EOFShortNoteTruncationReport,
    analyze_guitarpro_short_note_truncation,
)
from .guitarpro_import import ArrangementKind

EOF_SHORT_NOTE_TRUNCATION_REPORT_PATH = Path("review") / "eof_short_note_truncation_report.json"


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


def build_project_eof_short_note_truncation_report(
    project_dir: Path,
    *,
    instrument: ArrangementKind = "bass",
    track_index: int | None = None,
    truncate_short_notes: bool = EOF_DEFAULT_TRUNCATE_SHORT_NOTES,
    truncate_short_chords: bool = EOF_DEFAULT_TRUNCATE_SHORT_CHORDS,
) -> EOFShortNoteTruncationReport:
    """Compare the project's registered GP score against EOF's default truncation preferences.

    The current immutable registered score is reparsed at the resolved arrangement track index.
    The result is evidence-only: it does not change notes, timing, review state, validation
    state, or package readiness. See ``eof_short_note_truncation_check`` for the ported EOF
    decision this reuses (``raynebc/editor-on-fire``, audited at the commit recorded there).
    """

    project = _project(project_dir)
    score_path = resolve_registered_score_for_eof(project)
    return analyze_guitarpro_short_note_truncation(
        score_path,
        instrument=instrument,
        track_index=track_index,
        truncate_short_notes=truncate_short_notes,
        truncate_short_chords=truncate_short_chords,
    )


def write_project_eof_short_note_truncation_report(
    project_dir: Path,
    *,
    instrument: ArrangementKind = "bass",
    track_index: int | None = None,
) -> tuple[Path, EOFShortNoteTruncationReport]:
    """Persist the latest advisory short-note-truncation comparison under the project review dir."""

    project = _project(project_dir)
    report = build_project_eof_short_note_truncation_report(
        project,
        instrument=instrument,
        track_index=track_index,
    )
    destination = project / EOF_SHORT_NOTE_TRUNCATION_REPORT_PATH
    _atomic_write(destination, report.model_dump_json(indent=2) + "\n")
    return destination, report
