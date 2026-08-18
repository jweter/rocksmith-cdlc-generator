from __future__ import annotations

from itertools import combinations
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .score_role_composition import ScoreRoleCompositionPlan, ScoreRoleCompositionSelection
from .score_source import ArrangementRole
from .source_import import SourceNoteEvent, SourceTrack

OverlapKind = Literal["exact_duplicate", "coincident_start", "duration_overlap"]
_TIME_EPSILON_SECONDS = 1e-9


class CompositionNoteReference(BaseModel):
    """Stable source-track/event reference for one overlap participant."""

    model_config = ConfigDict(frozen=True)

    source_track_index: int = Field(ge=0)
    event_index: int = Field(ge=0)
    start_seconds: float = Field(ge=0)
    duration_seconds: float = Field(gt=0)
    midi: int = Field(ge=0, le=127)
    string_index: int | None = Field(default=None, ge=0)
    fret: int | None = Field(default=None, ge=0)


class CompositionOverlap(BaseModel):
    """One explicit cross-track overlap that downstream work must not silently resolve."""

    model_config = ConfigDict(frozen=True)

    kind: OverlapKind
    left: CompositionNoteReference
    right: CompositionNoteReference


class RoleCompositionOverlapSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: ArrangementRole
    source_track_indices: list[int]
    overlap_count: int = Field(ge=0)
    exact_duplicate_count: int = Field(ge=0)
    coincident_start_count: int = Field(ge=0)
    duration_overlap_count: int = Field(ge=0)
    overlaps: list[CompositionOverlap] = Field(default_factory=list)


class ScoreRoleCompositionOverlapReport(BaseModel):
    """Read-only overlap evidence for one exact provenance-bound composition plan."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    score_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    score_format: str
    roles: list[RoleCompositionOverlapSummary] = Field(default_factory=list)


def _same_time(left: float, right: float) -> bool:
    return abs(left - right) <= _TIME_EPSILON_SECONDS


def _note_reference(track: SourceTrack, event_index: int, note: SourceNoteEvent) -> CompositionNoteReference:
    return CompositionNoteReference(
        source_track_index=track.source_track_index,
        event_index=event_index,
        start_seconds=note.start_seconds,
        duration_seconds=note.duration_seconds,
        midi=note.midi,
        string_index=note.string_index,
        fret=note.fret,
    )


def _overlap_kind(left: SourceNoteEvent, right: SourceNoteEvent) -> OverlapKind:
    same_start = _same_time(left.start_seconds, right.start_seconds)
    if (
        same_start
        and _same_time(left.duration_seconds, right.duration_seconds)
        and left.midi == right.midi
        and left.string_index == right.string_index
        and left.fret == right.fret
    ):
        return "exact_duplicate"
    if same_start:
        return "coincident_start"
    return "duration_overlap"


def _pair_overlaps(left_track: SourceTrack, right_track: SourceTrack) -> list[CompositionOverlap]:
    overlaps: list[CompositionOverlap] = []
    right_floor = 0

    for left_index, left in enumerate(left_track.notes):
        left_start = left.start_seconds
        left_end = left.start_seconds + left.duration_seconds

        while right_floor < len(right_track.notes):
            candidate = right_track.notes[right_floor]
            candidate_end = candidate.start_seconds + candidate.duration_seconds
            if candidate_end > left_start:
                break
            right_floor += 1

        right_index = right_floor
        while right_index < len(right_track.notes):
            right = right_track.notes[right_index]
            if right.start_seconds >= left_end:
                break
            right_end = right.start_seconds + right.duration_seconds
            if right_end > left_start:
                overlaps.append(
                    CompositionOverlap(
                        kind=_overlap_kind(left, right),
                        left=_note_reference(left_track, left_index, left),
                        right=_note_reference(right_track, right_index, right),
                    )
                )
            right_index += 1

    return overlaps


def _summary_for_selection(
    selection: ScoreRoleCompositionSelection,
    tracks_by_index: dict[int, SourceTrack],
) -> RoleCompositionOverlapSummary:
    missing = [index for index in selection.source_track_indices if index not in tracks_by_index]
    if missing:
        raise ValueError(
            f"{selection.role.value} overlap analysis is missing selected source track(s): {missing}"
        )

    selected_tracks = [tracks_by_index[index] for index in selection.source_track_indices]
    overlaps: list[CompositionOverlap] = []
    for left_track, right_track in combinations(selected_tracks, 2):
        overlaps.extend(_pair_overlaps(left_track, right_track))

    kind_order: dict[OverlapKind, int] = {
        "exact_duplicate": 0,
        "coincident_start": 1,
        "duration_overlap": 2,
    }
    overlaps.sort(
        key=lambda item: (
            min(item.left.start_seconds, item.right.start_seconds),
            kind_order[item.kind],
            item.left.source_track_index,
            item.left.event_index,
            item.right.source_track_index,
            item.right.event_index,
        )
    )

    return RoleCompositionOverlapSummary(
        role=selection.role,
        source_track_indices=list(selection.source_track_indices),
        overlap_count=len(overlaps),
        exact_duplicate_count=sum(item.kind == "exact_duplicate" for item in overlaps),
        coincident_start_count=sum(item.kind == "coincident_start" for item in overlaps),
        duration_overlap_count=sum(item.kind == "duration_overlap" for item in overlaps),
        overlaps=overlaps,
    )


def analyze_score_role_composition_overlaps(
    plan: ScoreRoleCompositionPlan,
    tracks: list[SourceTrack],
) -> ScoreRoleCompositionOverlapReport:
    """Expose cross-track overlap evidence without merging or choosing musical material.

    Only notes from different explicitly selected source tracks are compared. Exact
    duplicates, simultaneous starts, and sustained interval overlaps are reported as
    provenance-bearing evidence. No note is discarded, shortened, preferred, or granted
    review authority by this analysis.
    """

    indexes = [track.source_track_index for track in tracks]
    if len(indexes) != len(set(indexes)):
        raise ValueError("composition overlap analysis requires unique source track indexes")
    tracks_by_index = {track.source_track_index: track for track in tracks}

    summaries = [
        _summary_for_selection(selection, tracks_by_index)
        for selection in sorted(plan.selections, key=lambda item: item.role.value)
    ]
    return ScoreRoleCompositionOverlapReport(
        score_sha256=plan.score_sha256,
        score_format=plan.score_format,
        roles=summaries,
    )
