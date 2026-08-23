from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

MarkState = Literal["questionable", "wrong"]
MarkScope = Literal["note", "chord"]
REVIEW_MARKS_PATH = Path("review/human_note_marks.json")


class HumanNoteReviewMark(BaseModel):
    arrangement: str
    event_index: int = Field(ge=0)
    source_start_seconds: float = Field(ge=0)
    midi: int = Field(ge=0, le=127)
    string_index: int | None = Field(default=None, ge=0)
    fret: int | None = Field(default=None, ge=0)
    state: MarkState
    scope: MarkScope = "note"
    marked_at: datetime


class HumanNoteReviewLayer(BaseModel):
    schema_version: int = 1
    source_sha256: str
    marks: list[HumanNoteReviewMark] = Field(default_factory=list)


def load_human_review_layer(project_dir: Path) -> HumanNoteReviewLayer | None:
    path = project_dir.resolve() / REVIEW_MARKS_PATH
    if not path.is_file():
        return None
    return HumanNoteReviewLayer.model_validate_json(path.read_text(encoding="utf-8"))


def load_current_human_review_layer(project_dir: Path, source_sha256: str) -> HumanNoteReviewLayer | None:
    layer = load_human_review_layer(project_dir)
    if layer is None or layer.source_sha256 != source_sha256:
        return None
    return layer


def mark_event(
    project_dir: Path,
    *,
    source_sha256: str,
    arrangement: str,
    event_index: int,
    source_start_seconds: float,
    midi: int,
    string_index: int | None,
    fret: int | None,
    state: MarkState,
    scope: MarkScope = "note",
) -> HumanNoteReviewLayer:
    project = project_dir.resolve()
    current = load_current_human_review_layer(project, source_sha256)
    marks = [] if current is None else list(current.marks)
    marks = [m for m in marks if not (m.arrangement == arrangement and m.event_index == event_index)]
    marks.append(
        HumanNoteReviewMark(
            arrangement=arrangement,
            event_index=event_index,
            source_start_seconds=source_start_seconds,
            midi=midi,
            string_index=string_index,
            fret=fret,
            state=state,
            scope=scope,
            marked_at=datetime.now(timezone.utc),
        )
    )
    marks.sort(key=lambda m: (m.arrangement, m.source_start_seconds, m.event_index))
    layer = HumanNoteReviewLayer(source_sha256=source_sha256, marks=marks)
    path = project / REVIEW_MARKS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(layer.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return layer


def clear_event_mark(project_dir: Path, *, source_sha256: str, arrangement: str, event_index: int) -> HumanNoteReviewLayer:
    project = project_dir.resolve()
    current = load_current_human_review_layer(project, source_sha256)
    marks = [] if current is None else [m for m in current.marks if not (m.arrangement == arrangement and m.event_index == event_index)]
    layer = HumanNoteReviewLayer(source_sha256=source_sha256, marks=marks)
    path = project / REVIEW_MARKS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(layer.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return layer
