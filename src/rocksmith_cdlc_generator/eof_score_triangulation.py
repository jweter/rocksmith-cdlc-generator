from __future__ import annotations

from pathlib import Path
from statistics import median
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .eof_bridge import resolve_registered_score_for_eof
from .guitarpro_import import ArrangementKind, GuitarProImportError, import_guitarpro
from .hashing import sha256_file
from .source_import import ImportedSource, SourceNoteEvent, SourceTrack


EOF_SCORE_TRIANGULATION_REPORT_PATH = Path("review") / "eof_score_triangulation_report.json"
_ROLES: tuple[ArrangementKind, ...] = ("bass", "lead", "rhythm")
_ONSET_MATCH_TOLERANCE_SECONDS = 0.075


class ScoreRoleComparison(BaseModel):
    """Read-only structural comparison of the registered and alternate GP role."""

    model_config = ConfigDict(frozen=True)

    instrument: ArrangementKind
    registered_track_index: int = Field(ge=0)
    alternate_track_index: int = Field(ge=0)
    registered_track_name: str | None = None
    alternate_track_name: str | None = None
    registered_note_count: int = Field(ge=0)
    alternate_note_count: int = Field(ge=0)
    registered_first_playable_seconds: float = Field(ge=0)
    alternate_first_playable_seconds: float = Field(ge=0)
    first_playable_delta_seconds: float
    tuning_match: bool
    tempo_event_count_match: bool
    time_signature_count_match: bool
    coordinate_prefix_matches: int = Field(ge=0)
    coordinate_prefix_compared: int = Field(ge=0)
    onset_prefix_matches: int = Field(ge=0)
    onset_prefix_compared: int = Field(ge=0)
    median_prefix_onset_delta_seconds: float | None = None
    max_prefix_onset_delta_seconds: float | None = None
    warnings: list[str] = Field(default_factory=list)

    @property
    def structurally_close(self) -> bool:
        return (
            self.tuning_match
            and self.coordinate_prefix_matches == self.coordinate_prefix_compared
            and self.onset_prefix_matches == self.onset_prefix_compared
        )


class EOFScoreTriangulationReport(BaseModel):
    """Project-local comparison of a private alternate GP score with the registered score."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    registered_score_path: str
    registered_score_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    alternate_score_path: str
    alternate_score_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    alternate_score_filename: str
    roles: list[ScoreRoleComparison]
    unavailable_roles: list[str] = Field(default_factory=list)
    evidence_note: str = (
        "Private alternate Guitar Pro comparison. Advisory evidence only; neither score silently replaces chart authority."
    )


def _single_track(source: ImportedSource) -> SourceTrack:
    if len(source.tracks) != 1:
        raise ValueError("role import must contain exactly one selected track")
    return source.tracks[0]


def _coordinate(note: SourceNoteEvent) -> tuple[int | None, int | None, int]:
    return (note.string_index, note.fret, note.midi)


def _compare_role(
    registered: ImportedSource,
    alternate: ImportedSource,
    *,
    instrument: ArrangementKind,
    prefix_limit: int = 96,
) -> ScoreRoleComparison:
    left = _single_track(registered)
    right = _single_track(alternate)
    left_notes = left.notes
    right_notes = right.notes
    compared = min(prefix_limit, len(left_notes), len(right_notes))
    coordinate_matches = sum(
        1
        for a, b in zip(left_notes[:compared], right_notes[:compared])
        if _coordinate(a) == _coordinate(b)
    )
    onset_deltas = [
        b.start_seconds - a.start_seconds
        for a, b in zip(left_notes[:compared], right_notes[:compared])
    ]
    onset_matches = sum(1 for value in onset_deltas if abs(value) <= _ONSET_MATCH_TOLERANCE_SECONDS)

    warnings: list[str] = []
    if len(left_notes) != len(right_notes):
        warnings.append(
            f"note count differs: registered {len(left_notes)} vs alternate {len(right_notes)}"
        )
    if coordinate_matches != compared:
        warnings.append(
            f"first {compared} events contain {compared - coordinate_matches} pitch/string/fret disagreement(s)"
        )
    if onset_matches != compared:
        warnings.append(
            f"first {compared} events contain {compared - onset_matches} source-time disagreement(s) over "
            f"{_ONSET_MATCH_TOLERANCE_SECONDS:.3f}s"
        )

    return ScoreRoleComparison(
        instrument=instrument,
        registered_track_index=left.source_track_index,
        alternate_track_index=right.source_track_index,
        registered_track_name=left.name,
        alternate_track_name=right.name,
        registered_note_count=len(left_notes),
        alternate_note_count=len(right_notes),
        registered_first_playable_seconds=left_notes[0].start_seconds,
        alternate_first_playable_seconds=right_notes[0].start_seconds,
        first_playable_delta_seconds=right_notes[0].start_seconds - left_notes[0].start_seconds,
        tuning_match=list(left.tuning_midi or []) == list(right.tuning_midi or []),
        tempo_event_count_match=len(registered.tempo_events) == len(alternate.tempo_events),
        time_signature_count_match=len(registered.time_signatures) == len(alternate.time_signatures),
        coordinate_prefix_matches=coordinate_matches,
        coordinate_prefix_compared=compared,
        onset_prefix_matches=onset_matches,
        onset_prefix_compared=compared,
        median_prefix_onset_delta_seconds=median(onset_deltas) if onset_deltas else None,
        max_prefix_onset_delta_seconds=max((abs(value) for value in onset_deltas), default=None),
        warnings=warnings,
    )


def build_project_eof_score_triangulation_report(
    project_dir: Path,
    alternate_score_path: Path,
) -> EOFScoreTriangulationReport:
    """Triangulate a private alternate GP score against the project's registered GP score.

    This intentionally compares source structure before any recording-clock mapping. It is
    complementary to EOF recording-clock parity: if two GP sources agree here but the final
    mapped chart disagrees with EOF/audio, the defect is downstream of GP interpretation.
    """

    project = project_dir.expanduser().resolve()
    if not (project / "project.json").is_file():
        raise FileNotFoundError(f"Not a CDLC project: {project}")
    registered_score = resolve_registered_score_for_eof(project)
    alternate_score = alternate_score_path.expanduser().resolve()
    if not alternate_score.is_file():
        raise FileNotFoundError(alternate_score)
    if alternate_score.suffix.lower() not in {".gp3", ".gp4", ".gp5"}:
        raise ValueError("alternate score must be Guitar Pro 3, 4, or 5")

    roles: list[ScoreRoleComparison] = []
    unavailable: list[str] = []
    for role in _ROLES:
        try:
            registered = import_guitarpro(registered_score, instrument=role)
            alternate = import_guitarpro(alternate_score, instrument=role)
        except (GuitarProImportError, ValueError) as exc:
            unavailable.append(f"{role}: {exc}")
            continue
        roles.append(_compare_role(registered, alternate, instrument=role))

    if not roles:
        raise ValueError("no Bass, Lead, or Rhythm role could be compared between the two Guitar Pro scores")

    return EOFScoreTriangulationReport(
        registered_score_path=str(registered_score),
        registered_score_sha256=sha256_file(registered_score),
        alternate_score_path=str(alternate_score),
        alternate_score_sha256=sha256_file(alternate_score),
        alternate_score_filename=alternate_score.name,
        roles=roles,
        unavailable_roles=unavailable,
    )


def write_project_eof_score_triangulation_report(
    project_dir: Path,
    alternate_score_path: Path,
) -> tuple[Path, EOFScoreTriangulationReport]:
    project = project_dir.expanduser().resolve()
    report = build_project_eof_score_triangulation_report(project, alternate_score_path)
    destination = project / EOF_SCORE_TRIANGULATION_REPORT_PATH
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.tmp")
    temporary.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    temporary.replace(destination)
    return destination, report


def load_current_project_eof_score_triangulation_report(
    project_dir: Path,
) -> EOFScoreTriangulationReport | None:
    project = project_dir.expanduser().resolve()
    destination = project / EOF_SCORE_TRIANGULATION_REPORT_PATH
    if not destination.is_file():
        return None
    report = EOFScoreTriangulationReport.model_validate_json(destination.read_text(encoding="utf-8"))
    registered_score = resolve_registered_score_for_eof(project)
    if sha256_file(registered_score) != report.registered_score_sha256:
        raise ValueError("alternate-score triangulation report is stale for the registered GP score")
    alternate = Path(report.alternate_score_path)
    if not alternate.is_file() or sha256_file(alternate) != report.alternate_score_sha256:
        raise ValueError("alternate-score triangulation report is stale because the alternate GP file moved or changed")
    return report
