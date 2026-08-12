from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from .musicxml_import import import_project_musicxml
from .musicxml_inspection import MusicXMLPartInspection, inspect_musicxml_source

ArrangementKind = Literal["lead", "rhythm", "bass"]


class MusicXMLArrangementSelection(BaseModel):
    instrument: ArrangementKind
    part_index: int = Field(ge=0)


class MusicXMLArrangementManifestEntry(BaseModel):
    instrument: ArrangementKind
    part_index: int
    part_id: str
    part_name: str
    tuning_midi: list[int] | None = None
    pitched_note_count: int
    output_json: str


class MusicXMLArrangementImportManifest(BaseModel):
    schema_version: int = 1
    source_filename: str
    source_sha256: str
    arrangements: list[MusicXMLArrangementManifestEntry]


class MusicXMLMultiImportResult(BaseModel):
    source_filename: str
    source_sha256: str
    outputs: dict[ArrangementKind, str]
    manifest_path: str


def _part_by_index(parts: list[MusicXMLPartInspection]) -> dict[int, MusicXMLPartInspection]:
    return {part.part_index: part for part in parts}


def _project_relative(project_dir: Path, path: Path) -> str:
    project_dir = project_dir.resolve()
    path = path.resolve()
    try:
        return path.relative_to(project_dir).as_posix()
    except ValueError as exc:
        raise ValueError(f"Imported arrangement output escaped project directory: {path}") from exc


def import_project_musicxml_arrangements(
    project_dir: Path,
    musicxml_path: Path,
    *,
    selections: list[MusicXMLArrangementSelection],
) -> MusicXMLMultiImportResult:
    """Import explicitly selected Lead/Rhythm/Bass parts from one MusicXML score.

    Human part selection is authoritative. This orchestration layer never guesses
    missing roles and rejects duplicate roles or duplicate source parts. After all
    selected imports succeed, it writes one project-local manifest that binds each
    arrangement role to the exact inspected MusicXML part and normalized output.
    """

    if not selections:
        raise ValueError("At least one MusicXML arrangement selection is required")

    roles = [selection.instrument for selection in selections]
    if len(set(roles)) != len(roles):
        raise ValueError("Each arrangement role may be selected at most once")

    part_indices = [selection.part_index for selection in selections]
    if len(set(part_indices)) != len(part_indices):
        raise ValueError("The same MusicXML part cannot be assigned to multiple arrangement roles")

    project_dir = project_dir.resolve()
    inspection = inspect_musicxml_source(musicxml_path)
    parts_by_index = _part_by_index(inspection.parts)
    unknown = sorted(set(part_indices) - set(parts_by_index))
    if unknown:
        raise ValueError(f"MusicXML part index out of range: {unknown}")

    outputs: dict[ArrangementKind, str] = {}
    manifest_entries: list[MusicXMLArrangementManifestEntry] = []
    for selection in selections:
        output = import_project_musicxml(
            project_dir,
            musicxml_path,
            part_index=selection.part_index,
            instrument=selection.instrument,
        )
        output_path = Path(output).resolve()
        relative_output = _project_relative(project_dir, output_path)
        outputs[selection.instrument] = str(output_path)

        part = parts_by_index[selection.part_index]
        manifest_entries.append(
            MusicXMLArrangementManifestEntry(
                instrument=selection.instrument,
                part_index=part.part_index,
                part_id=part.part_id,
                part_name=part.name,
                tuning_midi=part.tuning_midi,
                pitched_note_count=part.pitched_note_count,
                output_json=relative_output,
            )
        )

    manifest = MusicXMLArrangementImportManifest(
        source_filename=inspection.source_filename,
        source_sha256=inspection.source_sha256,
        arrangements=manifest_entries,
    )
    manifest_dir = project_dir / "sources" / "imported"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / f"musicxml-arrangements-{inspection.source_sha256[:12]}.json"
    manifest_path.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")

    return MusicXMLMultiImportResult(
        source_filename=inspection.source_filename,
        source_sha256=inspection.source_sha256,
        outputs=outputs,
        manifest_path=str(manifest_path),
    )
