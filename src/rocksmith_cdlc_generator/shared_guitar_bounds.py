from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from .guitar_authoring import GuitarAuthoringChart, GuitarAuthoringNote, GuitarChordEvent
from .hashing import sha256_file
from .models import ProjectManifest
from .shared_guitar import SharedGuitarDraftManifest, SharedGuitarRole, build_project_shared_guitar_chart


BOUNDARY_ALGORITHM_VERSION = 1
_BOUNDARY_TEMPLATE = "review/{arrangement}_projection_boundary.json"


class SharedGuitarBoundaryReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: int = 1
    algorithm_version: int = BOUNDARY_ALGORITHM_VERSION
    arrangement: SharedGuitarRole
    recording_duration_seconds: float = Field(gt=0)
    omitted_single_notes: int = Field(ge=0)
    omitted_chords: int = Field(ge=0)
    clipped_single_notes: int = Field(ge=0)
    clipped_chords: int = Field(ge=0)
    clipped_chord_notes: int = Field(ge=0)


def _boundary_path(project: Path, arrangement: SharedGuitarRole) -> Path:
    return project / _BOUNDARY_TEMPLATE.format(arrangement=arrangement)


def shared_guitar_boundary_is_current(project_dir: Path, arrangement: SharedGuitarRole) -> bool:
    project = project_dir.expanduser().resolve()
    path = _boundary_path(project, arrangement)
    if not path.is_file():
        return False
    try:
        report = SharedGuitarBoundaryReport.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    return (
        report.algorithm_version == BOUNDARY_ALGORITHM_VERSION
        and report.arrangement == arrangement
    )


def _clip_note(
    note: GuitarAuthoringNote,
    duration: float,
) -> tuple[GuitarAuthoringNote | None, bool]:
    if note.start_seconds >= duration:
        return None, False
    max_duration = duration - note.start_seconds
    if note.duration_seconds <= max_duration:
        return note, False
    return note.model_copy(update={"duration_seconds": max(0.001, max_duration)}), True


def _bound_chart(
    chart: GuitarAuthoringChart,
    duration: float,
) -> tuple[GuitarAuthoringChart, SharedGuitarBoundaryReport]:
    singles: list[GuitarAuthoringNote] = []
    omitted_single = clipped_single = 0
    for note in chart.single_notes:
        bounded, clipped = _clip_note(note, duration)
        if bounded is None:
            omitted_single += 1
            continue
        clipped_single += int(clipped)
        singles.append(bounded)

    chords: list[GuitarChordEvent] = []
    omitted_chords = clipped_chords = clipped_chord_notes = 0
    for chord in chart.chords:
        if chord.start_seconds >= duration:
            omitted_chords += 1
            continue

        bounded_notes: list[GuitarAuthoringNote] = []
        for note in chord.notes:
            bounded, clipped = _clip_note(note, duration)
            if bounded is None:
                continue
            clipped_chord_notes += int(clipped)
            bounded_notes.append(bounded)

        if len(bounded_notes) < 2:
            omitted_chords += 1
            continue

        max_sustain = duration - chord.start_seconds
        sustain = min(chord.sustain_seconds, max_sustain)
        clipped = chord.sustain_seconds > max_sustain
        clipped_chords += int(clipped)
        chords.append(
            chord.model_copy(
                update={
                    "sustain_seconds": max(0.001, sustain),
                    "notes": bounded_notes,
                }
            )
        )

    omitted_total = omitted_single + omitted_chords
    clipped_total = clipped_single + clipped_chords + clipped_chord_notes
    warnings = list(chart.warnings)
    if omitted_total or clipped_total:
        warnings.append(
            "Recording boundary: "
            f"omitted {omitted_total} trailing {chart.arrangement} event(s) whose projected onset fell outside the recording; "
            f"clipped {clipped_total} sustain(s) at the recording end. Source score material remains preserved upstream."
        )

    bounded_chart = chart.model_copy(
        update={
            "single_notes": singles,
            "chords": chords,
            "warnings": warnings,
        }
    )
    report = SharedGuitarBoundaryReport(
        arrangement=chart.arrangement,
        recording_duration_seconds=duration,
        omitted_single_notes=omitted_single,
        omitted_chords=omitted_chords,
        clipped_single_notes=clipped_single,
        clipped_chords=clipped_chords,
        clipped_chord_notes=clipped_chord_notes,
    )
    return bounded_chart, report


def build_project_shared_guitar_chart_bounded(
    project_dir: Path,
    *,
    arrangement: SharedGuitarRole,
) -> Path:
    """Build Lead/Rhythm and bound derived playable events to the recording duration."""

    project = project_dir.expanduser().resolve()
    chart_path = build_project_shared_guitar_chart(project, arrangement=arrangement)
    duration = float(ProjectManifest.load(project).source_metadata.duration_seconds)
    chart = GuitarAuthoringChart.model_validate_json(chart_path.read_text(encoding="utf-8"))
    bounded_chart, report = _bound_chart(chart, duration)
    bounded_chart.write_json(chart_path)

    boundary_path = _boundary_path(project, arrangement)
    boundary_path.parent.mkdir(parents=True, exist_ok=True)
    boundary_path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")

    draft_manifest_path = project / "charts" / f"{arrangement}_shared_timeline.json"
    draft_manifest = SharedGuitarDraftManifest.read_json(draft_manifest_path)
    draft_manifest.model_copy(
        update={"chart_sha256": sha256_file(chart_path)}
    ).write_json(draft_manifest_path)
    return chart_path
