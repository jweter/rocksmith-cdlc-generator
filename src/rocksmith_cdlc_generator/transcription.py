from __future__ import annotations

import csv
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, Field, model_validator


class NoteEvent(BaseModel):
    start: float = Field(ge=0.0)
    duration: float = Field(gt=0.0)
    midi: int = Field(ge=0, le=127)
    confidence: float = Field(ge=0.0, le=1.0)
    pitch_confidence: float = Field(ge=0.0, le=1.0)
    timing_confidence: float = Field(ge=0.0, le=1.0)
    review_required: bool = False

    @property
    def end(self) -> float:
        return self.start + self.duration


class BassTranscription(BaseModel):
    schema_version: int = 1
    engine: str
    engine_version: str | None = None
    source_path: str
    sample_rate_hz: int
    notes: list[NoteEvent]

    @model_validator(mode="after")
    def validate_note_order(self) -> "BassTranscription":
        starts = [note.start for note in self.notes]
        if any(current < previous for previous, current in zip(starts, starts[1:])):
            raise ValueError("Note events must be ordered by start time")
        return self


class BassTranscriber(Protocol):
    name: str
    version: str | None

    def transcribe(self, audio_path: Path) -> BassTranscription:
        """Transcribe a mono-dominant bass signal into validated note events."""
        ...


def write_transcription(transcription: BassTranscription, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(transcription.model_dump_json(indent=2), encoding="utf-8")


def read_transcription(path: Path) -> BassTranscription:
    return BassTranscription.model_validate_json(path.read_text(encoding="utf-8"))


def write_notes_csv(transcription: BassTranscription, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "start",
                "duration",
                "midi",
                "confidence",
                "pitch_confidence",
                "timing_confidence",
                "review_required",
            ]
        )
        for note in transcription.notes:
            writer.writerow(
                [
                    f"{note.start:.6f}",
                    f"{note.duration:.6f}",
                    note.midi,
                    f"{note.confidence:.6f}",
                    f"{note.pitch_confidence:.6f}",
                    f"{note.timing_confidence:.6f}",
                    str(note.review_required).lower(),
                ]
            )
