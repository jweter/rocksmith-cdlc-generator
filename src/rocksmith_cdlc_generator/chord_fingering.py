from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .arrangement_edit_history import record_arrangement_review_edit
from .hashing import sha256_file
from .reviewed_positions import (
    POSITION_REVIEW_PATH,
    ReviewedPositionDecision,
    ReviewedPositionLayer,
    _current_fanout,
    _source_event,
    load_current_reviewed_positions,
)
from .score_mapping_review import load_score_for_mapping_review
from .song_preview import SongPreviewSnapshot

GuitarRole = Literal["lead", "rhythm"]


class ChordFingeringNote(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_index: int = Field(ge=0)
    string_index: int = Field(ge=0)
    fret: int = Field(ge=0)


class ChordFingeringCandidate(BaseModel):
    model_config = ConfigDict(frozen=True)

    arrangement: GuitarRole
    source_track_index: int = Field(ge=0)
    event_indices: list[int] = Field(min_length=2)
    start_seconds: float = Field(ge=0)

    @model_validator(mode="after")
    def unique_events(self) -> "ChordFingeringCandidate":
        if len(self.event_indices) != len(set(self.event_indices)):
            raise ValueError("chord candidate contains duplicate events")
        return self


def chord_candidate_for_event(
    project_dir: Path,
    preview: SongPreviewSnapshot,
    *,
    arrangement: GuitarRole,
    event_index: int,
    onset_tolerance_seconds: float = 0.001,
) -> ChordFingeringCandidate | None:
    """Return the authoritative source-onset chord containing one selected event.

    Preview event times live on the recording clock and may carry per-event reviewed
    timing overrides. Chord membership is instead a property of the immutable score
    event group, so candidate detection deliberately uses the same source-note onsets
    and tolerance that final fingering acceptance validates.
    """

    if onset_tolerance_seconds <= 0:
        raise ValueError("onset tolerance must be positive")
    lane = next((item for item in preview.arrangements if item.instrument == arrangement), None)
    if lane is None:
        raise ValueError(f"preview has no {arrangement} arrangement")
    selected_preview = next((item for item in lane.notes if item.event_index == event_index), None)
    if selected_preview is None:
        raise IndexError(f"{arrangement} event index is not present in preview")

    project = project_dir.expanduser().resolve()
    entry, track, selected_source = _source_event(project, arrangement, event_index)
    if entry.source_track_index != lane.part_index:
        raise ValueError(f"{arrangement} preview track is stale for current fan-out authority")

    event_indices = [
        index
        for index, note in enumerate(track.notes)
        if abs(note.start_seconds - selected_source.start_seconds) <= onset_tolerance_seconds
    ]
    if len(event_indices) < 2:
        return None

    preview_by_index = {item.event_index: item for item in lane.notes}
    missing = [index for index in event_indices if index not in preview_by_index]
    if missing:
        raise ValueError(f"{arrangement} preview is missing current source chord events")
    display_start = min(preview_by_index[index].start_seconds for index in event_indices)
    return ChordFingeringCandidate(
        arrangement=arrangement,
        source_track_index=entry.source_track_index,
        event_indices=event_indices,
        start_seconds=display_start,
    )


def accept_chord_fingering(
    project_dir: Path,
    *,
    arrangement: GuitarRole,
    notes: list[ChordFingeringNote],
    source_onset_tolerance_seconds: float = 0.001,
) -> ReviewedPositionLayer:
    """Atomically accept physical positions for one simultaneous Lead/Rhythm chord.

    The canonical reviewed-position layer remains the only string/fret authority. This
    operation validates the entire chord first and writes that layer once, preventing a
    half-accepted fingering if one note is invalid.
    """

    if source_onset_tolerance_seconds <= 0:
        raise ValueError("source onset tolerance must be positive")
    if len(notes) < 2:
        raise ValueError("chord fingering requires at least two notes")
    event_indices = [item.event_index for item in notes]
    if len(event_indices) != len(set(event_indices)):
        raise ValueError("chord fingering contains duplicate event indices")
    strings = [item.string_index for item in notes]
    if len(strings) != len(set(strings)):
        raise ValueError("chord fingering cannot place multiple notes on one string")

    project = project_dir.expanduser().resolve()
    fanout_path, _manifest = _current_fanout(project)
    score = load_score_for_mapping_review(project)

    validated: list[tuple[ChordFingeringNote, object, object, object]] = []
    starts: list[float] = []
    source_track_index: int | None = None
    for fingering in notes:
        entry, track, note = _source_event(project, arrangement, fingering.event_index)
        if source_track_index is None:
            source_track_index = entry.source_track_index
        elif source_track_index != entry.source_track_index:
            raise ValueError("chord fingering events do not share one source track")
        if track.tuning_midi is None:
            raise ValueError(f"{arrangement} chord fingering requires explicit source tuning")
        if fingering.string_index >= len(track.tuning_midi):
            raise ValueError(
                f"string index {fingering.string_index} is outside the {len(track.tuning_midi)}-string tuning"
            )
        if int(track.tuning_midi[fingering.string_index]) + fingering.fret != note.midi:
            raise ValueError(
                f"event {fingering.event_index} string/fret position does not produce source MIDI pitch"
            )
        starts.append(note.start_seconds)
        validated.append((fingering, entry, track, note))

    if max(starts) - min(starts) > source_onset_tolerance_seconds:
        raise ValueError("selected events are not one simultaneous source chord")

    current = load_current_reviewed_positions(project)
    decisions = [] if current is None else list(current.decisions)
    replacing = {(arrangement, source_track_index, item.event_index) for item in notes}
    decisions = [
        item
        for item in decisions
        if (item.arrangement, item.source_track_index, item.event_index) not in replacing
    ]
    accepted_at = datetime.now(timezone.utc)
    for fingering, entry, _track, note in validated:
        decisions.append(
            ReviewedPositionDecision(
                arrangement=arrangement,
                source_track_index=entry.source_track_index,
                event_index=fingering.event_index,
                source_start_seconds=note.start_seconds,
                midi=note.midi,
                string_index=fingering.string_index,
                fret=fingering.fret,
                accepted_at=accepted_at,
            )
        )
    decisions.sort(key=lambda item: (item.arrangement, item.source_track_index, item.event_index))
    layer = ReviewedPositionLayer(
        score_sha256=score.source_sha256,
        score_format=score.source_format,
        fanout_manifest_path=fanout_path.relative_to(project).as_posix(),
        fanout_manifest_sha256=sha256_file(fanout_path),
        decisions=decisions,
    )
    record_arrangement_review_edit(
        project,
        kind="chord_fingering",
        writes={POSITION_REVIEW_PATH: layer.model_dump_json(indent=2) + "\n"},
        score_sha256=layer.score_sha256,
        score_format=layer.score_format,
        fanout_manifest_path=layer.fanout_manifest_path,
        fanout_manifest_sha256=layer.fanout_manifest_sha256,
    )
    return layer
