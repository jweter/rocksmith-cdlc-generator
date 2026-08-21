from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .source_import import ImportedSource, SourceTrack

SourcePositionStatus = Literal["missing", "candidate", "inconsistent"]


class FretboardPositionCandidate(BaseModel):
    """One pitch-correct physical position for a source note under current tuning."""

    model_config = ConfigDict(frozen=True)

    string_index: int = Field(ge=0)
    fret: int = Field(ge=0)


class FretboardEventCandidates(BaseModel):
    """Read-only candidate positions for one imported source event."""

    model_config = ConfigDict(frozen=True)

    event_index: int = Field(ge=0)
    midi: int = Field(ge=0, le=127)
    source_string_index: int | None = Field(default=None, ge=0)
    source_fret: int | None = Field(default=None, ge=0)
    candidates: list[FretboardPositionCandidate]

    @property
    def ambiguous(self) -> bool:
        return len(self.candidates) > 1

    @property
    def source_position_status(self) -> SourcePositionStatus:
        """Classify source coordinates against the complete pitch-correct candidate set."""

        if self.source_string_index is None or self.source_fret is None:
            return "missing"
        if any(
            candidate.string_index == self.source_string_index
            and candidate.fret == self.source_fret
            for candidate in self.candidates
        ):
            return "candidate"
        return "inconsistent"


class FretboardCandidateInventory(BaseModel):
    """Pitch-correct search space for future global fretboard-position optimization."""

    model_config = ConfigDict(frozen=True)

    schema_version: int = 2
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_track_index: int = Field(ge=0)
    tuning_midi: list[int] = Field(min_length=1)
    max_fret: int = Field(ge=0)
    events: list[FretboardEventCandidates]

    @property
    def ambiguous_event_count(self) -> int:
        return sum(event.ambiguous for event in self.events)

    @property
    def source_position_match_count(self) -> int:
        return sum(event.source_position_status == "candidate" for event in self.events)

    @property
    def missing_source_position_count(self) -> int:
        return sum(event.source_position_status == "missing" for event in self.events)

    @property
    def inconsistent_source_position_count(self) -> int:
        return sum(event.source_position_status == "inconsistent" for event in self.events)


def _track(source: ImportedSource, source_track_index: int) -> SourceTrack:
    track = next(
        (item for item in source.tracks if item.source_track_index == source_track_index),
        None,
    )
    if track is None:
        raise ValueError(f"source track {source_track_index} is not present in imported source")
    if not track.tuning_midi:
        raise ValueError("fretboard candidate inventory requires explicit source tuning")
    return track


def build_fretboard_candidate_inventory(
    source: ImportedSource,
    *,
    source_track_index: int,
    max_fret: int = 24,
) -> FretboardCandidateInventory:
    """Enumerate all pitch-correct note positions without choosing among them.

    This is an evidence/read-model primitive for future sequence optimization. It does
    not rewrite source positions, infer accepted fingering, apply EOF behavior, or
    weaken reviewed-position and human playability authority. Source coordinates are
    retained and classified only as matching, missing, or inconsistent with the legal
    pitch-correct search space.
    """

    if max_fret < 0:
        raise ValueError("max_fret must be non-negative")

    track = _track(source, source_track_index)
    tuning = list(track.tuning_midi or [])
    events: list[FretboardEventCandidates] = []

    for event_index, note in enumerate(track.notes):
        candidates = [
            FretboardPositionCandidate(string_index=string_index, fret=note.midi - open_midi)
            for string_index, open_midi in enumerate(tuning)
            if 0 <= note.midi - open_midi <= max_fret
        ]
        if not candidates:
            raise ValueError(
                f"event {event_index} MIDI {note.midi} has no playable position within fret {max_fret}"
            )

        events.append(
            FretboardEventCandidates(
                event_index=event_index,
                midi=note.midi,
                source_string_index=note.string_index,
                source_fret=note.fret,
                candidates=candidates,
            )
        )

    return FretboardCandidateInventory(
        source_sha256=source.provenance.source_sha256,
        source_track_index=source_track_index,
        tuning_midi=tuning,
        max_fret=max_fret,
        events=events,
    )
