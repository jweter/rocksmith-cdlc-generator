from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from .musicxml_import import import_project_musicxml
from .musicxml_inspection import inspect_musicxml_source

ArrangementKind = Literal["lead", "rhythm", "bass"]


class MusicXMLArrangementSelection(BaseModel):
    instrument: ArrangementKind
    part_index: int = Field(ge=0)


class MusicXMLMultiImportResult(BaseModel):
    source_filename: str
    source_sha256: str
    outputs: dict[ArrangementKind, str]


def import_project_musicxml_arrangements(
    project_dir: Path,
    musicxml_path: Path,
    *,
    selections: list[MusicXMLArrangementSelection],
) -> MusicXMLMultiImportResult:
    """Import explicitly selected Lead/Rhythm/Bass parts from one MusicXML score.

    Human part selection is authoritative. This orchestration layer never guesses
    missing roles and rejects duplicate roles or duplicate source parts.
    """

    if not selections:
        raise ValueError("At least one MusicXML arrangement selection is required")

    roles = [selection.instrument for selection in selections]
    if len(set(roles)) != len(roles):
        raise ValueError("Each arrangement role may be selected at most once")

    part_indices = [selection.part_index for selection in selections]
    if len(set(part_indices)) != len(part_indices):
        raise ValueError("The same MusicXML part cannot be assigned to multiple arrangement roles")

    inspection = inspect_musicxml_source(musicxml_path)
    available = {part.part_index for part in inspection.parts}
    unknown = sorted(set(part_indices) - available)
    if unknown:
        raise ValueError(f"MusicXML part index out of range: {unknown}")

    outputs: dict[ArrangementKind, str] = {}
    for selection in selections:
        output = import_project_musicxml(
            project_dir,
            musicxml_path,
            part_index=selection.part_index,
            instrument=selection.instrument,
        )
        outputs[selection.instrument] = str(output)

    return MusicXMLMultiImportResult(
        source_filename=inspection.source_filename,
        source_sha256=inspection.source_sha256,
        outputs=outputs,
    )
