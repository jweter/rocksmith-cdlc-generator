from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .reviewed_export_events import ReviewedExportNote


class ExactTieFold(BaseModel):
    """One mechanically proven tie chain rooted at its first source event."""

    model_config = ConfigDict(frozen=True)

    primary_event_index: int = Field(ge=0)
    continuation_event_indices: tuple[int, ...]
    source_duration_seconds: float = Field(gt=0)
    reviewed_duration_seconds: float = Field(gt=0)


class ReviewedTieFoldPlan(BaseModel):
    """Read-only exact-tie folding instructions for reviewed authoring consumers."""

    model_config = ConfigDict(frozen=True)

    primary_event_by_event: dict[int, int]
    folds_by_primary: dict[int, ExactTieFold]

    @property
    def continuation_event_indices(self) -> frozenset[int]:
        return frozenset(
            event_index
            for fold in self.folds_by_primary.values()
            for event_index in fold.continuation_event_indices
        )


def _same_physical_note(left: ReviewedExportNote, right: ReviewedExportNote) -> bool:
    return (
        left.position_ready
        and right.position_ready
        and left.string_index is not None
        and right.string_index is not None
        and left.fret is not None
        and right.fret is not None
        and left.string_index == right.string_index
        and left.fret == right.fret
        and left.midi == right.midi
    )


def _is_tie_only(note: ReviewedExportNote) -> bool:
    return set(note.techniques) == {"tie"}


def plan_exact_reviewed_tie_folds(
    notes: list[ReviewedExportNote],
    *,
    adjacency_tolerance_seconds: float = 1e-6,
) -> ReviewedTieFoldPlan:
    """Plan safe tie folds without changing persisted or reviewed authority.

    A continuation is foldable only when its sole technique is ``tie`` and exactly
    one earlier root note on the same physical string/fret and pitch ends at the tie
    onset in *both* the source and promoted-reviewed clocks. Gaps, overlaps,
    duplicate candidates, position changes, and tie events carrying any additional
    technique remain unfolded so the existing authoring gates continue to fail
    closed.
    """

    if adjacency_tolerance_seconds < 0:
        raise ValueError("adjacency tolerance must be non-negative")

    source_starts = [note.source_start_seconds for note in notes]
    reviewed_starts = [note.reviewed_start_seconds for note in notes]
    if source_starts != sorted(source_starts) or reviewed_starts != sorted(
        reviewed_starts
    ):
        raise ValueError(
            "reviewed tie folding requires ordered source and reviewed notes"
        )

    by_event_index: dict[int, ReviewedExportNote] = {}
    primary_event_by_event: dict[int, int] = {}
    source_end_by_primary: dict[int, float] = {}
    reviewed_end_by_primary: dict[int, float] = {}
    continuation_indices_by_primary: dict[int, list[int]] = {}

    for note in notes:
        event_index = note.source_event_index
        if event_index in by_event_index:
            raise ValueError(
                "reviewed tie folding requires unique source-event indexes"
            )
        by_event_index[event_index] = note

        if _is_tie_only(note):
            candidates = [
                primary_index
                for primary_index in source_end_by_primary
                if _same_physical_note(by_event_index[primary_index], note)
                and abs(
                    source_end_by_primary[primary_index] - note.source_start_seconds
                )
                <= adjacency_tolerance_seconds
                and abs(
                    reviewed_end_by_primary[primary_index] - note.reviewed_start_seconds
                )
                <= adjacency_tolerance_seconds
            ]
            if len(candidates) == 1:
                primary_index = candidates[0]
                primary_event_by_event[event_index] = primary_index
                continuation_indices_by_primary.setdefault(primary_index, []).append(
                    event_index
                )
                source_end_by_primary[primary_index] = (
                    note.source_start_seconds + note.source_duration_seconds
                )
                reviewed_end_by_primary[primary_index] = (
                    note.reviewed_start_seconds + note.reviewed_duration_seconds
                )
                continue

        primary_event_by_event[event_index] = event_index
        source_end_by_primary[event_index] = (
            note.source_start_seconds + note.source_duration_seconds
        )
        reviewed_end_by_primary[event_index] = (
            note.reviewed_start_seconds + note.reviewed_duration_seconds
        )

    folds_by_primary: dict[int, ExactTieFold] = {}
    for primary_index, continuation_indices in continuation_indices_by_primary.items():
        primary = by_event_index[primary_index]
        folds_by_primary[primary_index] = ExactTieFold(
            primary_event_index=primary_index,
            continuation_event_indices=tuple(continuation_indices),
            source_duration_seconds=(
                source_end_by_primary[primary_index] - primary.source_start_seconds
            ),
            reviewed_duration_seconds=(
                reviewed_end_by_primary[primary_index] - primary.reviewed_start_seconds
            ),
        )

    return ReviewedTieFoldPlan(
        primary_event_by_event=primary_event_by_event,
        folds_by_primary=folds_by_primary,
    )
