from __future__ import annotations

from bisect import bisect_right
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .alignment import AlignmentReport, map_source_time
from .hashing import sha256_file
from .models import ProjectManifest
from .reviewed_positions import _current_fanout, _source_event
from .score_mapping_review import load_score_for_mapping_review
from .score_source import ArrangementRole
from .shared_timeline import alignment_for_role, load_current_shared_timeline
from .source_import import ImportedSource

ArrangementRoleName = Literal["bass", "lead", "rhythm"]
EVENT_TIMING_REVIEW_PATH = Path("review") / "reviewed_event_timing.json"
SHARED_TIMELINE_PATH = Path("analysis") / "shared_timeline.json"


class ReviewedEventTimingDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    arrangement: ArrangementRoleName
    source_track_index: int = Field(ge=0)
    event_index: int = Field(ge=0)
    source_start_seconds: float = Field(ge=0)
    source_duration_seconds: float = Field(gt=0)
    midi: int = Field(ge=0, le=127)
    reviewed_start_seconds: float = Field(ge=0)
    reviewed_duration_seconds: float = Field(gt=0)
    accepted_at: datetime

    @property
    def reviewed_end_seconds(self) -> float:
        return self.reviewed_start_seconds + self.reviewed_duration_seconds


class ReviewedEventTimingLayer(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    score_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    score_format: str
    fanout_manifest_path: str
    fanout_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    shared_timeline_path: str
    shared_timeline_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    decisions: list[ReviewedEventTimingDecision] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_event_keys(self) -> "ReviewedEventTimingLayer":
        keys = [
            (item.arrangement, item.source_track_index, item.event_index)
            for item in self.decisions
        ]
        if len(keys) != len(set(keys)):
            raise ValueError("reviewed event timing layer contains duplicate event decisions")
        return self

    def decision_for(
        self,
        arrangement: ArrangementRoleName,
        source_track_index: int,
        event_index: int,
    ) -> ReviewedEventTimingDecision | None:
        return next(
            (
                item
                for item in self.decisions
                if item.arrangement == arrangement
                and item.source_track_index == source_track_index
                and item.event_index == event_index
            ),
            None,
        )


def _shared_timeline(project: Path) -> Path:
    load_current_shared_timeline(project)
    path = project / SHARED_TIMELINE_PATH
    if not path.is_file():
        raise FileNotFoundError("Current shared timeline is not available")
    return path


def _map_recording_time_to_source(report: AlignmentReport, audio_time_seconds: float) -> float:
    anchors = report.anchors
    if len(anchors) < 2:
        raise ValueError("shared alignment needs at least two anchors")
    if audio_time_seconds <= anchors[0].audio_time_seconds:
        first, second = anchors[0], anchors[1]
    elif audio_time_seconds >= anchors[-1].audio_time_seconds:
        first, second = anchors[-2], anchors[-1]
    else:
        ys = [item.audio_time_seconds for item in anchors]
        right = bisect_right(ys, audio_time_seconds)
        first, second = anchors[right - 1], anchors[right]
    span = second.audio_time_seconds - first.audio_time_seconds
    ratio = (audio_time_seconds - first.audio_time_seconds) / span
    return first.source_time_seconds + ratio * (second.source_time_seconds - first.source_time_seconds)


def validate_decision_identity(
    project_dir: Path,
    decision: ReviewedEventTimingDecision,
) -> None:
    project = project_dir.expanduser().resolve()
    entry, _track, note = _source_event(project, decision.arrangement, decision.event_index)
    if entry.source_track_index != decision.source_track_index:
        raise ValueError("Reviewed event timing source track is stale")
    if note.midi != decision.midi:
        raise ValueError("Reviewed event timing MIDI identity is stale")
    if abs(note.start_seconds - decision.source_start_seconds) > 1e-6:
        raise ValueError("Reviewed event timing source onset identity is stale")
    if abs(note.duration_seconds - decision.source_duration_seconds) > 1e-6:
        raise ValueError("Reviewed event timing source duration identity is stale")


def load_current_reviewed_event_timing(project_dir: Path) -> ReviewedEventTimingLayer | None:
    project = project_dir.expanduser().resolve()
    destination = project / EVENT_TIMING_REVIEW_PATH
    if not destination.is_file():
        return None

    score = load_score_for_mapping_review(project)
    fanout_path, _manifest = _current_fanout(project)
    timeline_path = _shared_timeline(project)
    layer = ReviewedEventTimingLayer.model_validate_json(destination.read_text(encoding="utf-8"))

    if layer.score_sha256 != score.source_sha256 or layer.score_format != score.source_format:
        raise ValueError("Reviewed event timing layer is stale for the registered score")
    if layer.fanout_manifest_path != fanout_path.relative_to(project).as_posix():
        raise ValueError("Reviewed event timing layer points at a stale score fan-out")
    if layer.fanout_manifest_sha256 != sha256_file(fanout_path):
        raise ValueError("Reviewed event timing layer is stale for the current score fan-out")
    if layer.shared_timeline_path != timeline_path.relative_to(project).as_posix():
        raise ValueError("Reviewed event timing layer points at a stale shared timeline")
    if layer.shared_timeline_sha256 != sha256_file(timeline_path):
        raise ValueError("Reviewed event timing layer is stale for the current shared timeline")
    for decision in layer.decisions:
        validate_decision_identity(project, decision)
    return layer


def current_reviewed_event_timing_sha256(project_dir: Path) -> str | None:
    project = project_dir.expanduser().resolve()
    layer = load_current_reviewed_event_timing(project)
    if layer is None:
        return None
    return sha256_file(project / EVENT_TIMING_REVIEW_PATH)


def set_reviewed_event_timing(
    project_dir: Path,
    *,
    arrangement: ArrangementRoleName,
    event_index: int,
    start_seconds: float,
    duration_seconds: float,
) -> ReviewedEventTimingLayer:
    """Accept one explicit recording-clock onset/duration correction without mutating source data."""

    project = project_dir.expanduser().resolve()
    if start_seconds < 0:
        raise ValueError("reviewed event start must be non-negative")
    if duration_seconds <= 0:
        raise ValueError("reviewed event duration must be positive")

    project_manifest = ProjectManifest.load(project)
    recording_duration = project_manifest.source_metadata.duration_seconds
    if start_seconds + duration_seconds > recording_duration + 1e-6:
        raise ValueError("reviewed event timing extends beyond the recording duration")

    fanout_path, _manifest = _current_fanout(project)
    timeline_path = _shared_timeline(project)
    score = load_score_for_mapping_review(project)
    entry, _track, note = _source_event(project, arrangement, event_index)
    alignment = alignment_for_role(project, ArrangementRole(arrangement))

    original_start = map_source_time(alignment, note.start_seconds)
    original_end = map_source_time(alignment, note.start_seconds + note.duration_seconds)
    if original_end <= original_start:
        raise ValueError("current shared timeline produces a non-positive source event duration")

    current = load_current_reviewed_event_timing(project)
    decisions = [] if current is None else list(current.decisions)
    key = (arrangement, entry.source_track_index, event_index)
    decisions = [
        item
        for item in decisions
        if (item.arrangement, item.source_track_index, item.event_index) != key
    ]
    decisions.append(
        ReviewedEventTimingDecision(
            arrangement=arrangement,
            source_track_index=entry.source_track_index,
            event_index=event_index,
            source_start_seconds=note.start_seconds,
            source_duration_seconds=note.duration_seconds,
            midi=note.midi,
            reviewed_start_seconds=float(start_seconds),
            reviewed_duration_seconds=float(duration_seconds),
            accepted_at=datetime.now(timezone.utc),
        )
    )
    decisions.sort(key=lambda item: (item.arrangement, item.source_track_index, item.event_index))

    layer = ReviewedEventTimingLayer(
        score_sha256=score.source_sha256,
        score_format=score.source_format,
        fanout_manifest_path=fanout_path.relative_to(project).as_posix(),
        fanout_manifest_sha256=sha256_file(fanout_path),
        shared_timeline_path=timeline_path.relative_to(project).as_posix(),
        shared_timeline_sha256=sha256_file(timeline_path),
        decisions=decisions,
    )
    destination = project / EVENT_TIMING_REVIEW_PATH
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(layer.model_dump_json(indent=2) + "\n", encoding="utf-8")
    temporary.replace(destination)
    return layer


def timing_overrides_for_arrangement(
    project_dir: Path,
    *,
    arrangement: ArrangementRoleName,
    source_track_index: int,
) -> dict[int, tuple[float, float]]:
    layer = load_current_reviewed_event_timing(project_dir)
    if layer is None:
        return {}
    return {
        item.event_index: (item.reviewed_start_seconds, item.reviewed_duration_seconds)
        for item in layer.decisions
        if item.arrangement == arrangement and item.source_track_index == source_track_index
    }


def apply_reviewed_event_timing_to_source(
    project_dir: Path,
    source: ImportedSource,
    *,
    arrangement: ArrangementRoleName,
    source_track_index: int,
) -> tuple[ImportedSource, set[int]]:
    """Return a copied source whose reviewed events map back to accepted recording-clock timing."""

    project = project_dir.expanduser().resolve()
    overrides = timing_overrides_for_arrangement(
        project,
        arrangement=arrangement,
        source_track_index=source_track_index,
    )
    copied = source.model_copy(deep=True)
    if not overrides:
        return copied, set()

    track = next(
        (
            item
            for item in copied.tracks
            if item.instrument == arrangement and item.source_track_index == source_track_index
        ),
        None,
    )
    if track is None:
        raise ValueError(f"Expected current {arrangement} track for reviewed event timing overlay")
    alignment = alignment_for_role(project, ArrangementRole(arrangement))
    applied: set[int] = set()
    for event_index, (reviewed_start, reviewed_duration) in overrides.items():
        if event_index >= len(track.notes):
            raise ValueError("Reviewed event timing index is stale for current fan-out")
        reviewed_end = reviewed_start + reviewed_duration
        source_start = _map_recording_time_to_source(alignment, reviewed_start)
        source_end = _map_recording_time_to_source(alignment, reviewed_end)
        if source_start < 0 or source_end <= source_start:
            raise ValueError("Reviewed recording-clock timing cannot be represented on the current source timeline")
        note = track.notes[event_index]
        note.start_seconds = source_start
        note.duration_seconds = source_end - source_start
        applied.add(event_index)
    return copied, applied
