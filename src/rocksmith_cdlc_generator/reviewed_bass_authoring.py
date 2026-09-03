from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .reviewed_export_events import (
    ReviewedExportArrangement,
    ReviewedExportNote,
    reviewed_export_arrangement,
)
from .reviewed_tie_folding import plan_exact_reviewed_tie_folds, rebase_bend_points_for_tie_fold
from .score_source import ArrangementRole
from .source_import import SourceBendPoint, SourceTrustClass

_AUTHORING_TRUST = frozenset({SourceTrustClass.symbolic_verified, SourceTrustClass.user_confirmed})


class ReviewedBassAuthoringNote(BaseModel):
    """One Bass note that is safe to hand to a Rocksmith authoring consumer."""

    model_config = ConfigDict(frozen=True)

    source_event_index: int = Field(ge=0)
    continuation_source_event_indices: list[int] = Field(default_factory=list)
    time_seconds: float = Field(ge=0)
    duration_seconds: float = Field(gt=0)
    midi: int = Field(ge=0, le=127)
    string_index: int = Field(ge=0, le=3)
    fret: int = Field(ge=0)
    techniques: list[str] = Field(default_factory=list)
    bend_points: list[SourceBendPoint] = Field(default_factory=list)
    slide_target_fret: int | None = Field(default=None, ge=0)
    link_next: bool = False
    import_confidence: float = Field(ge=0, le=1)
    trust_class: SourceTrustClass

    @model_validator(mode="after")
    def continuation_lineage_is_unique(self) -> "ReviewedBassAuthoringNote":
        if self.continuation_source_event_indices != sorted(self.continuation_source_event_indices):
            raise ValueError("Bass tie continuation source-event indexes must remain ordered")
        if len(self.continuation_source_event_indices) != len(set(self.continuation_source_event_indices)):
            raise ValueError("Bass tie continuation source-event indexes must be unique")
        if self.source_event_index in self.continuation_source_event_indices:
            raise ValueError("Bass tie continuation lineage cannot repeat its primary event")
        return self


class ReviewedBassAuthoringInput(BaseModel):
    """Read-only Bass authoring input backed by promoted reviewed timing and source evidence."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    source_track_index: int = Field(ge=0)
    source_output_json: str
    source_output_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    recording_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    score_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    tuning_midi: tuple[int, int, int, int]
    notes: list[ReviewedBassAuthoringNote]
    human_confirmed_timing: Literal[True] = True

    @model_validator(mode="after")
    def notes_are_ordered(self) -> "ReviewedBassAuthoringInput":
        times = [note.time_seconds for note in self.notes]
        if times != sorted(times):
            raise ValueError("reviewed Bass authoring notes must remain ordered")
        if not self.notes:
            raise ValueError("reviewed Bass authoring input requires at least one note")
        return self


def _validated_bass_note(
    note: ReviewedExportNote,
    tuning: tuple[int, int, int, int],
    *,
    allow_exact_tie_continuation: bool = False,
) -> ReviewedBassAuthoringNote:
    if note.review_required and not allow_exact_tie_continuation:
        raise ValueError(f"Bass source event {note.source_event_index} still requires human review")
    if note.trust_class not in _AUTHORING_TRUST:
        raise ValueError(f"Bass source event {note.source_event_index} does not have accepted source trust")
    if not note.position_ready or note.string_index is None or note.fret is None:
        raise ValueError(f"Bass source event {note.source_event_index} has no confirmed string/fret position")
    if note.string_index > 3:
        raise ValueError(f"Bass source event {note.source_event_index} has an invalid string index")
    if tuning[note.string_index] + note.fret != note.midi:
        raise ValueError(f"Bass source event {note.source_event_index} string/fret position does not match pitch")
    return ReviewedBassAuthoringNote(
        source_event_index=note.source_event_index,
        time_seconds=note.reviewed_start_seconds,
        duration_seconds=note.reviewed_duration_seconds,
        midi=note.midi,
        string_index=note.string_index,
        fret=note.fret,
        techniques=list(note.techniques),
        bend_points=list(note.bend_points),
        slide_target_fret=note.slide_target_fret,
        link_next=note.link_next,
        import_confidence=note.import_confidence,
        trust_class=note.trust_class,
    )


def bass_authoring_input_from_reviewed_export(
    arrangement: ReviewedExportArrangement,
) -> ReviewedBassAuthoringInput:
    """Validate a reviewed export projection for Bass authoring without writing any artifact."""

    if arrangement.role is not ArrangementRole.bass:
        raise ValueError("reviewed Bass authoring input requires the Bass arrangement")
    if arrangement.tuning_midi is None or len(arrangement.tuning_midi) != 4:
        raise ValueError("reviewed Bass authoring input requires an explicit four-string tuning")
    tuning = tuple(int(value) for value in arrangement.tuning_midi)
    if any(current <= previous for previous, current in zip(tuning, tuning[1:])):
        raise ValueError("reviewed Bass tuning must be strictly ascending")

    tie_plan = plan_exact_reviewed_tie_folds(arrangement.notes)
    continuation_indexes = tie_plan.continuation_event_indices
    notes: list[ReviewedBassAuthoringNote] = []
    for note in arrangement.notes:
        if note.source_event_index in continuation_indexes:
            # Validate every continuation's trust, physical position, and pitch before
            # allowing the contextual fold to remove its redundant note head.
            _validated_bass_note(
                note,
                tuning,
                allow_exact_tie_continuation=True,
            )
            continue

        validated = _validated_bass_note(note, tuning)
        fold = tie_plan.folds_by_primary.get(note.source_event_index)
        if fold is not None:
            validated = validated.model_copy(
                update={
                    "duration_seconds": fold.reviewed_duration_seconds,
                    "continuation_source_event_indices": list(fold.continuation_event_indices),
                    "bend_points": rebase_bend_points_for_tie_fold(
                        validated.bend_points,
                        original_reviewed_duration_seconds=note.reviewed_duration_seconds,
                        folded_reviewed_duration_seconds=fold.reviewed_duration_seconds,
                    ),
                }
            )
        notes.append(validated)
    return ReviewedBassAuthoringInput(
        source_track_index=arrangement.source_track_index,
        source_output_json=arrangement.source_output_json,
        source_output_sha256=arrangement.source_output_sha256,
        recording_sha256=arrangement.recording_sha256,
        score_sha256=arrangement.score_sha256,
        tuning_midi=tuning,
        notes=notes,
        human_confirmed_timing=True,
    )


def reviewed_bass_authoring_input(project_dir: Path) -> ReviewedBassAuthoringInput:
    """Build the current read-only Bass authoring input from reviewed project authority.

    This is an adapter only. It writes no Rocksmith XML, changes no canonical chart or timing,
    and does not bypass source, musical-review, validation, or packaging gates.
    """

    arrangement = reviewed_export_arrangement(project_dir, ArrangementRole.bass)
    return bass_authoring_input_from_reviewed_export(arrangement)
