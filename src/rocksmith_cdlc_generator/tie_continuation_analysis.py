from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .source_import import ImportedSource, SourceNoteEvent

TieClassification = Literal["exact_continuation", "ambiguous_or_orphan"]


class TieContinuationCandidate(BaseModel):
    event_index: int = Field(ge=0)
    predecessor_event_index: int | None = Field(default=None, ge=0)
    string_index: int | None = Field(default=None, ge=0)
    fret: int | None = Field(default=None, ge=0)
    midi: int = Field(ge=0, le=127)
    start_seconds: float = Field(ge=0)
    classification: TieClassification


class TieContinuationAnalysis(BaseModel):
    """Read-only classification of imported tie events for one normalized source track."""

    schema_version: int = 1
    source_track_index: int = Field(ge=0)
    tie_event_count: int = Field(ge=0)
    exact_continuation_count: int = Field(ge=0)
    ambiguous_or_orphan_count: int = Field(ge=0)
    candidates: list[TieContinuationCandidate] = Field(default_factory=list)


def _same_physical_note(left: SourceNoteEvent, right: SourceNoteEvent) -> bool:
    return (
        left.string_index is not None
        and right.string_index is not None
        and left.fret is not None
        and right.fret is not None
        and left.string_index == right.string_index
        and left.fret == right.fret
        and left.midi == right.midi
    )


def analyze_imported_tie_continuations(
    imported: ImportedSource,
    *,
    adjacency_tolerance_seconds: float = 1e-6,
) -> TieContinuationAnalysis:
    """Classify explicit imported ties without changing source or review authority.

    A tie is an exact continuation candidate only when exactly one earlier event on the
    same physical string/fret and MIDI pitch ends at the tie onset within the supplied
    tolerance. Ambiguous, orphaned, positionless, or non-adjacent ties remain unresolved.
    This function never removes events, changes duration, or clears ``review_required``.
    """

    if adjacency_tolerance_seconds < 0:
        raise ValueError("adjacency tolerance must be non-negative")
    if len(imported.tracks) != 1:
        raise ValueError("Tie continuation analysis requires exactly one normalized source track")

    track = imported.tracks[0]
    candidates: list[TieContinuationCandidate] = []
    tie_count = 0
    exact_count = 0

    for event_index, note in enumerate(track.notes):
        if "tie" not in note.techniques:
            continue
        tie_count += 1
        predecessors = [
            (previous_index, previous)
            for previous_index, previous in enumerate(track.notes[:event_index])
            if _same_physical_note(previous, note)
            and abs(
                (previous.start_seconds + previous.duration_seconds)
                - note.start_seconds
            )
            <= adjacency_tolerance_seconds
        ]
        if len(predecessors) == 1:
            predecessor_index, _predecessor = predecessors[0]
            classification: TieClassification = "exact_continuation"
            exact_count += 1
        else:
            predecessor_index = None
            classification = "ambiguous_or_orphan"

        candidates.append(
            TieContinuationCandidate(
                event_index=event_index,
                predecessor_event_index=predecessor_index,
                string_index=note.string_index,
                fret=note.fret,
                midi=note.midi,
                start_seconds=note.start_seconds,
                classification=classification,
            )
        )

    return TieContinuationAnalysis(
        source_track_index=track.source_track_index,
        tie_event_count=tie_count,
        exact_continuation_count=exact_count,
        ambiguous_or_orphan_count=tie_count - exact_count,
        candidates=candidates,
    )


def exact_tie_review_exempt_event_indexes(imported: ImportedSource) -> set[int]:
    """Return tie event indexes that no longer need a human tie-continuation decision.

    Exemption is deliberately narrower than ``exact_continuation`` classification. The
    imported event must still be marked review-required and ``tie`` must be its only
    imported technique. Any additional technique keeps the event reviewable so this
    mechanical continuation rule cannot silently accept bends, slides, articulation,
    or another semantic decision that happens to share the same event.

    The returned indexes are read-model evidence only; source bytes and review flags are
    never mutated here.
    """

    analysis = analyze_imported_tie_continuations(imported)
    track = imported.tracks[0]
    exact_indexes = {
        item.event_index
        for item in analysis.candidates
        if item.classification == "exact_continuation"
    }
    return {
        event_index
        for event_index in exact_indexes
        if track.notes[event_index].review_required
        and track.notes[event_index].techniques == ["tie"]
    }
