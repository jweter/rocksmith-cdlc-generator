from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .reviewed_export_events import (
    ReviewedExportArrangement,
    ReviewedExportChordGroup,
    ReviewedExportNote,
    reviewed_export_arrangement,
)
from .reviewed_tie_folding import (
    ReviewedTieFoldPlan,
    plan_exact_reviewed_tie_folds,
    rebase_bend_points_for_tie_fold,
)
from .score_source import ArrangementRole
from .source_import import SourceBendPoint, SourceTrustClass

_AUTHORING_TRUST = frozenset({SourceTrustClass.symbolic_verified, SourceTrustClass.user_confirmed})
_GUITAR_ROLES = frozenset({ArrangementRole.lead, ArrangementRole.rhythm})


class ReviewedGuitarAuthoringNote(BaseModel):
    """One reviewed Lead/Rhythm note safe for a downstream authoring consumer."""

    model_config = ConfigDict(frozen=True)

    source_event_index: int = Field(ge=0)
    continuation_source_event_indices: list[int] = Field(default_factory=list)
    time_seconds: float = Field(ge=0)
    duration_seconds: float = Field(gt=0)
    midi: int = Field(ge=0, le=127)
    string_index: int = Field(ge=0, le=5)
    fret: int = Field(ge=0)
    techniques: list[str] = Field(default_factory=list)
    bend_points: list[SourceBendPoint] = Field(default_factory=list)
    slide_target_fret: int | None = Field(default=None, ge=0)
    link_next: bool = False
    import_confidence: float = Field(ge=0, le=1)
    trust_class: SourceTrustClass

    @model_validator(mode="after")
    def continuation_lineage_is_unique(self) -> "ReviewedGuitarAuthoringNote":
        if self.continuation_source_event_indices != sorted(self.continuation_source_event_indices):
            raise ValueError("guitar tie continuation source-event indexes must remain ordered")
        if len(self.continuation_source_event_indices) != len(set(self.continuation_source_event_indices)):
            raise ValueError("guitar tie continuation source-event indexes must be unique")
        if self.source_event_index in self.continuation_source_event_indices:
            raise ValueError("guitar tie continuation lineage cannot repeat its primary event")
        return self


class ReviewedGuitarAuthoringChord(BaseModel):
    """Human-reviewed guitar chord identity expressed in source-event indices."""

    model_config = ConfigDict(frozen=True)

    source_event_indices: list[int] = Field(min_length=2)

    @model_validator(mode="after")
    def members_are_unique_and_ordered(self) -> "ReviewedGuitarAuthoringChord":
        if self.source_event_indices != sorted(self.source_event_indices):
            raise ValueError("reviewed guitar chord members must remain ordered")
        if len(self.source_event_indices) != len(set(self.source_event_indices)):
            raise ValueError("reviewed guitar chord contains duplicate source events")
        return self


class ReviewedGuitarAuthoringInput(BaseModel):
    """Read-only Lead/Rhythm authoring input backed by promoted reviewed authority."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    role: Literal[ArrangementRole.lead, ArrangementRole.rhythm]
    source_track_index: int = Field(ge=0)
    source_output_json: str
    source_output_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    recording_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    score_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    tuning_midi: tuple[int, int, int, int, int, int]
    notes: list[ReviewedGuitarAuthoringNote]
    chord_groups: list[ReviewedGuitarAuthoringChord] = Field(default_factory=list)
    human_confirmed_timing: Literal[True] = True

    @model_validator(mode="after")
    def notes_and_chords_are_consistent(self) -> "ReviewedGuitarAuthoringInput":
        if not self.notes:
            raise ValueError("reviewed guitar authoring input requires at least one note")
        times = [note.time_seconds for note in self.notes]
        if times != sorted(times):
            raise ValueError("reviewed guitar authoring notes must remain ordered")

        known = {note.source_event_index for note in self.notes}
        used: set[int] = set()
        for group in self.chord_groups:
            members = set(group.source_event_indices)
            if not members.issubset(known):
                raise ValueError("reviewed guitar chord references an unknown authoring note")
            if used.intersection(members):
                raise ValueError("one reviewed guitar source event cannot belong to multiple chords")
            used.update(members)
        return self


def _validated_guitar_note(
    note: ReviewedExportNote,
    tuning: tuple[int, int, int, int, int, int],
    role: ArrangementRole,
    *,
    allow_exact_tie_continuation: bool = False,
) -> ReviewedGuitarAuthoringNote:
    if note.review_required and not allow_exact_tie_continuation:
        raise ValueError(f"{role.value} source event {note.source_event_index} still requires human review")
    if note.trust_class not in _AUTHORING_TRUST:
        raise ValueError(f"{role.value} source event {note.source_event_index} does not have accepted source trust")
    if not note.position_ready or note.string_index is None or note.fret is None:
        raise ValueError(f"{role.value} source event {note.source_event_index} has no confirmed string/fret position")
    if note.string_index > 5:
        raise ValueError(f"{role.value} source event {note.source_event_index} has an invalid string index")
    if tuning[note.string_index] + note.fret != note.midi:
        raise ValueError(
            f"{role.value} source event {note.source_event_index} string/fret position does not match pitch"
        )
    return ReviewedGuitarAuthoringNote(
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


def _validated_chord(group: ReviewedExportChordGroup) -> ReviewedGuitarAuthoringChord:
    return ReviewedGuitarAuthoringChord(source_event_indices=list(group.source_event_indices))


def _folded_chord_groups(
    groups: list[ReviewedExportChordGroup],
    tie_plan: ReviewedTieFoldPlan,
) -> list[ReviewedGuitarAuthoringChord]:
    """Deduplicate only tie chords whose exact primary chord was already reviewed."""

    original_groups = {tuple(group.source_event_indices) for group in groups}
    emitted: set[tuple[int, ...]] = set()
    folded_groups: list[ReviewedGuitarAuthoringChord] = []

    for group in groups:
        original = tuple(group.source_event_indices)
        folded = tuple(
            sorted({tie_plan.primary_event_by_event[event_index] for event_index in group.source_event_indices})
        )
        if folded != original and folded not in original_groups:
            raise ValueError(
                "exact tie folding would alter reviewed guitar chord identity; "
                "review the mixed continuation chord explicitly"
            )
        if folded in emitted:
            continue
        emitted.add(folded)
        folded_groups.append(_validated_chord(ReviewedExportChordGroup(source_event_indices=list(folded))))

    return folded_groups


def guitar_authoring_input_from_reviewed_export(
    arrangement: ReviewedExportArrangement,
) -> ReviewedGuitarAuthoringInput:
    """Validate one reviewed Lead/Rhythm projection without writing authoring artifacts."""

    if arrangement.role not in _GUITAR_ROLES:
        raise ValueError("reviewed guitar authoring input requires Lead or Rhythm")
    if arrangement.tuning_midi is None or len(arrangement.tuning_midi) != 6:
        raise ValueError("reviewed guitar authoring input requires an explicit six-string tuning")
    tuning = tuple(int(value) for value in arrangement.tuning_midi)
    if any(current <= previous for previous, current in zip(tuning, tuning[1:])):
        raise ValueError("reviewed guitar tuning must be strictly ascending")

    tie_plan = plan_exact_reviewed_tie_folds(arrangement.notes)
    continuation_indexes = tie_plan.continuation_event_indices
    notes: list[ReviewedGuitarAuthoringNote] = []
    for note in arrangement.notes:
        if note.source_event_index in continuation_indexes:
            # Validate every continuation's trust, physical position, and pitch before
            # allowing the contextual fold to remove its redundant note head.
            _validated_guitar_note(
                note,
                tuning,
                arrangement.role,
                allow_exact_tie_continuation=True,
            )
            continue

        validated = _validated_guitar_note(note, tuning, arrangement.role)
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
    chords = _folded_chord_groups(arrangement.chord_groups, tie_plan)
    return ReviewedGuitarAuthoringInput(
        role=arrangement.role,
        source_track_index=arrangement.source_track_index,
        source_output_json=arrangement.source_output_json,
        source_output_sha256=arrangement.source_output_sha256,
        recording_sha256=arrangement.recording_sha256,
        score_sha256=arrangement.score_sha256,
        tuning_midi=tuning,
        notes=notes,
        chord_groups=chords,
        human_confirmed_timing=True,
    )


def reviewed_guitar_authoring_input(
    project_dir: Path,
    role: ArrangementRole,
) -> ReviewedGuitarAuthoringInput:
    """Build current read-only Lead/Rhythm authoring input from reviewed project authority.

    This adapter preserves explicit reviewed chord identity and writes no review or
    authoring authority. Resolving a current multi-track composition may refresh its
    deterministic composed-source cache. The adapter does not infer missing chord
    membership or fingering, create Rocksmith chord templates/XML, alter canonical
    charts/timing, package CDLC, or bypass source/musical/tone review gates.
    """

    if role not in _GUITAR_ROLES:
        raise ValueError("reviewed guitar authoring input requires Lead or Rhythm")
    arrangement = reviewed_export_arrangement(project_dir, role)
    return guitar_authoring_input_from_reviewed_export(arrangement)
