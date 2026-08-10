from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, Field, model_validator


class BeatEvent(BaseModel):
    time: float = Field(ge=0.0)
    beat: int = Field(ge=1)
    measure: int = Field(ge=1)
    bpm: float = Field(gt=0.0)
    confidence: float = Field(ge=0.0, le=1.0)
    is_downbeat: bool = False


class TempoMap(BaseModel):
    schema_version: int = 1
    engine: str
    engine_version: str | None = None
    sample_rate_hz: int = 44100
    time_signature_numerator: int = Field(default=4, ge=1)
    time_signature_denominator: int = Field(default=4, ge=1)
    beats: list[BeatEvent]

    @model_validator(mode="after")
    def validate_monotonic_timestamps(self) -> "TempoMap":
        times = [beat.time for beat in self.beats]
        if any(current <= previous for previous, current in zip(times, times[1:])):
            raise ValueError("Beat timestamps must be strictly increasing")
        return self

    @property
    def median_bpm(self) -> float | None:
        if not self.beats:
            return None
        values = sorted(beat.bpm for beat in self.beats)
        middle = len(values) // 2
        if len(values) % 2:
            return values[middle]
        return (values[middle - 1] + values[middle]) / 2.0


class BeatTracker(Protocol):
    """Adapter contract for any beat/downbeat analysis engine."""

    name: str
    version: str | None

    def analyze(self, audio_path: Path) -> TempoMap:
        """Analyze canonical project audio and return a validated tempo map."""
        ...


def write_tempo_map(tempo_map: TempoMap, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(tempo_map.model_dump_json(indent=2), encoding="utf-8")


def write_beats_csv(tempo_map: TempoMap, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["time", "beat", "measure", "bpm", "confidence", "is_downbeat"]
        )
        for event in tempo_map.beats:
            writer.writerow(
                [
                    f"{event.time:.6f}",
                    event.beat,
                    event.measure,
                    f"{event.bpm:.6f}",
                    f"{event.confidence:.6f}",
                    str(event.is_downbeat).lower(),
                ]
            )


def read_tempo_map(path: Path) -> TempoMap:
    return TempoMap.model_validate_json(path.read_text(encoding="utf-8"))
