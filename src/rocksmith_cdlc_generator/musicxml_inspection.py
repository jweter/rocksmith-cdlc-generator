from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from .hashing import sha256_file
from .musicxml_import import (
    _child,
    _children,
    _load_root,
    _local,
    _part_metadata,
    _part_score,
    _staff_tuning,
)


class MusicXMLPartInspection(BaseModel):
    part_index: int
    part_id: str
    name: str
    midi_programs: list[int] = Field(default_factory=list)
    tuning_midi: list[int] | None = None
    measure_count: int
    pitched_note_count: int
    rest_count: int
    lead_score: int
    rhythm_score: int
    bass_score: int


class MusicXMLSourceInspection(BaseModel):
    schema_version: int = 1
    source_filename: str
    source_sha256: str
    parts: list[MusicXMLPartInspection]


def inspect_musicxml_source(path: Path) -> MusicXMLSourceInspection:
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(f"MusicXML file not found: {path}")
    if path.suffix.lower() not in {".musicxml", ".xml", ".mxl"}:
        raise ValueError("MusicXML inspection supports .musicxml, .xml, and .mxl files")

    root = _load_root(path)
    if _local(root.tag) != "score-partwise":
        raise ValueError("Only score-partwise MusicXML is currently supported")

    metadata = _part_metadata(root)
    parts = [node for node in root if _local(node.tag) == "part"]
    if not parts:
        raise ValueError("MusicXML contains no parts")

    inspected: list[MusicXMLPartInspection] = []
    for index, part in enumerate(parts):
        part_id = part.attrib.get("id", "")
        meta = metadata.get(part_id, {})
        measures = _children(part, "measure")
        pitched_notes = 0
        rests = 0
        for note in (node for node in part.iter() if _local(node.tag) == "note"):
            if _child(note, "rest") is not None:
                rests += 1
            elif _child(note, "pitch") is not None:
                pitched_notes += 1

        inspected.append(
            MusicXMLPartInspection(
                part_index=index,
                part_id=part_id or f"part-{index}",
                name=str(meta.get("name") or part_id or f"Part {index}"),
                midi_programs=[int(value) for value in meta.get("programs", [])],
                tuning_midi=_staff_tuning(part),
                measure_count=len(measures),
                pitched_note_count=pitched_notes,
                rest_count=rests,
                lead_score=_part_score(part, meta, "lead"),
                rhythm_score=_part_score(part, meta, "rhythm"),
                bass_score=_part_score(part, meta, "bass"),
            )
        )

    return MusicXMLSourceInspection(
        source_filename=path.name,
        source_sha256=sha256_file(path),
        parts=inspected,
    )
