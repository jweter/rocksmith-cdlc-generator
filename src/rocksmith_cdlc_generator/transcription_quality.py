from __future__ import annotations

from statistics import mean

from pydantic import BaseModel, Field

from .transcription import BassTranscription


class BassTranscriptionReview(BaseModel):
    status: str
    note_count: int = Field(ge=0)
    mean_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    review_required_count: int = Field(ge=0)
    review_required_fraction: float = Field(ge=0.0, le=1.0)
    midi_min: int | None = Field(default=None, ge=0, le=127)
    midi_max: int | None = Field(default=None, ge=0, le=127)
    warnings: list[str] = Field(default_factory=list)


def review_bass_transcription(transcription: BassTranscription) -> BassTranscriptionReview:
    notes = transcription.notes
    if not notes:
        return BassTranscriptionReview(
            status="FAIL",
            note_count=0,
            review_required_count=0,
            review_required_fraction=0.0,
            warnings=["No bass notes were detected."],
        )

    review_required_count = sum(note.review_required for note in notes)
    review_fraction = review_required_count / len(notes)
    mean_confidence = mean(note.confidence for note in notes)
    midi_min = min(note.midi for note in notes)
    midi_max = max(note.midi for note in notes)

    warnings: list[str] = []
    if mean_confidence < 0.55:
        warnings.append(f"Mean transcription confidence is low ({mean_confidence:.2f}).")
    if review_fraction > 0.25:
        warnings.append(
            f"{review_fraction:.0%} of note events require review; inspect pitch/onset quality."
        )
    if midi_min < 28 or midi_max > 72:
        warnings.append(
            f"Detected range MIDI {midi_min}-{midi_max} extends beyond the expected practical bass range."
        )

    return BassTranscriptionReview(
        status="WARNING" if warnings else "PASS",
        note_count=len(notes),
        mean_confidence=mean_confidence,
        review_required_count=review_required_count,
        review_required_fraction=review_fraction,
        midi_min=midi_min,
        midi_max=midi_max,
        warnings=warnings,
    )
