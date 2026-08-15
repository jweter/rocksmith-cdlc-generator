from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
    preview: SongPreviewSnapshot,
    *,
    arrangement: GuitarRole,
    event_index: int,
    onset_tolerance_seconds: float = 0.001,
) -> ChordFingeringCandidate | None:
    """Return the simultaneous guitar-note group containing one selected event."""

    if onset_tolerance_seconds <= 0:
        raise ValueError("onset tolerance must be positive")
    lane = next((item for item in preview.arrangements if item.instrument == arrangement), None)
    if lane is None:
        raise ValueError(f"preview has no {arrangement} arrangement")
    selected = next((item for item in lane.notes if item.event_index == event_index), None)
    if selected is None:
        raise IndexError(f"{arrangement} event index is not present in preview")
    simultaneous = [
        item
        for item in lane.notes
        if abs(item.start_seconds - selected.start_seconds) <= onset_tolerance_seconds
    ]
    if len(simultaneous) < 2:
        return None
    return ChordFingeringCandidate(
        arrangement=arrangement,
        source_track_index=lane.part_index,
        event_indices=sorted(item.event_index for item in simultaneous),
        start_seconds=min(item.start_seconds for item in simultaneous),
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
    destination = project / POSITION_REVIEW_PATH
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(layer.model_dump_json(indent=2) + "\n", encoding="utf-8")
    temporary.replace(destination)
    return layer
