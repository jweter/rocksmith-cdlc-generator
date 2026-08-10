from __future__ import annotations

from statistics import mean, median, pstdev
from typing import Literal

from pydantic import BaseModel, Field

from .beats import TempoMap


class BeatGridReview(BaseModel):
    status: Literal["PASS", "WARNING", "FAIL"]
    beat_count: int = Field(ge=0)
    median_bpm: float | None = None
    mean_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    interval_cv: float | None = Field(default=None, ge=0.0)
    largest_interval_deviation_ms: float | None = Field(default=None, ge=0.0)
    warnings: list[str] = Field(default_factory=list)


def review_tempo_map(tempo_map: TempoMap) -> BeatGridReview:
    beats = tempo_map.beats
    warnings: list[str] = []
    if len(beats) < 2:
        return BeatGridReview(
            status="FAIL",
            beat_count=len(beats),
            median_bpm=tempo_map.median_bpm,
            warnings=["Fewer than two beats were detected."],
        )

    intervals = [b.time - a.time for a, b in zip(beats, beats[1:])]
    median_interval = median(intervals)
    mean_interval = mean(intervals)
    interval_cv = pstdev(intervals) / mean_interval if mean_interval else 0.0
    largest_deviation_ms = max(abs(value - median_interval) for value in intervals) * 1000.0
    confidence = mean(beat.confidence for beat in beats)

    if interval_cv > 0.15:
        warnings.append(f"Beat interval variation is high (CV={interval_cv:.3f}).")
    if largest_deviation_ms > 150.0:
        warnings.append(
            f"Largest beat interval deviation is {largest_deviation_ms:.1f} ms; inspect tempo drift or missed beats."
        )
    if confidence < 0.35:
        warnings.append(f"Mean beat salience confidence is low ({confidence:.2f}).")

    return BeatGridReview(
        status="WARNING" if warnings else "PASS",
        beat_count=len(beats),
        median_bpm=tempo_map.median_bpm,
        mean_confidence=confidence,
        interval_cv=interval_cv,
        largest_interval_deviation_ms=largest_deviation_ms,
        warnings=warnings,
    )
