from __future__ import annotations

from statistics import mean

from pydantic import BaseModel, Field

from .fret_mapping import BassMapping


class MappingReview(BaseModel):
    status: str
    note_count: int = Field(ge=0)
    unmapped_count: int = Field(ge=0)
    review_required_count: int = Field(ge=0)
    mean_mapping_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    max_fret_used: int | None = Field(default=None, ge=0)
    warnings: list[str] = []


def review_bass_mapping(mapping: BassMapping) -> MappingReview:
    notes = mapping.notes
    unmapped = [note for note in notes if not note.mapped]
    review_required = [note for note in notes if note.review_required]
    mapped = [note for note in notes if note.mapped]

    warnings: list[str] = []
    if unmapped:
        warnings.append(f"{len(unmapped)} note(s) cannot be played in the selected tuning/fret range.")
    if review_required:
        warnings.append(f"{len(review_required)} note(s) require mapping review.")

    mean_confidence = mean(note.mapping_confidence for note in mapped) if mapped else None
    if mean_confidence is not None and mean_confidence < 0.65:
        warnings.append(f"Mean mapping confidence is low ({mean_confidence:.2f}).")

    max_fret_used = max((note.fret for note in mapped if note.fret is not None), default=None)

    if unmapped:
        status = "FAIL"
    elif warnings:
        status = "WARNING"
    else:
        status = "PASS"

    return MappingReview(
        status=status,
        note_count=len(notes),
        unmapped_count=len(unmapped),
        review_required_count=len(review_required),
        mean_mapping_confidence=mean_confidence,
        max_fret_used=max_fret_used,
        warnings=warnings,
    )
