from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .beats import BeatEvent, TempoMap, read_tempo_map
from .hashing import sha256_file
from .models import ProjectManifest


class ReviewedTimingAnchor(BaseModel):
    model_config = ConfigDict(frozen=True)

    beat_index: int = Field(ge=0)
    original_time_seconds: float = Field(ge=0)
    reviewed_time_seconds: float = Field(ge=0)
    locked: bool = False


class ReviewedTiming(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    recording_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    tempo_map_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    anchors: list[ReviewedTimingAnchor]
    human_confirmed: bool = False

    @model_validator(mode="after")
    def validate_anchor_order(self) -> "ReviewedTiming":
        indices = [anchor.beat_index for anchor in self.anchors]
        if indices != sorted(indices) or len(indices) != len(set(indices)):
            raise ValueError("timing anchors must have unique ascending beat indices")
        times = [anchor.reviewed_time_seconds for anchor in self.anchors]
        if any(current <= previous for previous, current in zip(times, times[1:])):
            raise ValueError("reviewed timing anchors must remain strictly increasing")
        return self


REVIEW_PATH = Path("review") / "reviewed_timing.json"
PROMOTED_MAP_PATH = Path("analysis") / "reviewed_tempo_map.json"


def _tempo_path(project: Path) -> Path:
    return project / "analysis" / "tempo_map.json"


def _load_current_inputs(project_dir: Path) -> tuple[Path, ProjectManifest, TempoMap]:
    project = project_dir.expanduser().resolve()
    manifest = ProjectManifest.load(project)
    tempo_path = _tempo_path(project)
    if not tempo_path.is_file():
        raise FileNotFoundError("tempo analysis is required before timing review")
    return project, manifest, read_tempo_map(tempo_path)


def create_reviewed_timing(project_dir: Path) -> ReviewedTiming:
    project, manifest, tempo = _load_current_inputs(project_dir)
    tempo_path = _tempo_path(project)
    review = ReviewedTiming(
        recording_sha256=manifest.source_sha256,
        tempo_map_sha256=sha256_file(tempo_path),
        anchors=[
            ReviewedTimingAnchor(
                beat_index=index,
                original_time_seconds=beat.time,
                reviewed_time_seconds=beat.time,
            )
            for index, beat in enumerate(tempo.beats)
        ],
    )
    save_reviewed_timing(project, review)
    return review


def load_reviewed_timing(project_dir: Path, *, create: bool = False) -> ReviewedTiming:
    project, manifest, _tempo = _load_current_inputs(project_dir)
    path = project / REVIEW_PATH
    if not path.is_file():
        if create:
            return create_reviewed_timing(project)
        raise FileNotFoundError(path)
    review = ReviewedTiming.model_validate_json(path.read_text(encoding="utf-8"))
    if review.recording_sha256 != manifest.source_sha256:
        raise ValueError("reviewed timing belongs to a different recording")
    if review.tempo_map_sha256 != sha256_file(_tempo_path(project)):
        raise ValueError("reviewed timing is stale because the raw tempo map changed")
    return review


def save_reviewed_timing(project_dir: Path, review: ReviewedTiming) -> Path:
    project = project_dir.expanduser().resolve()
    path = project / REVIEW_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(review.model_dump_json(indent=2), encoding="utf-8")
    return path


def _replace_anchor(
    review: ReviewedTiming,
    beat_index: int,
    *,
    time_seconds: float | None = None,
    locked: bool | None = None,
) -> ReviewedTiming:
    anchors = list(review.anchors)
    if beat_index < 0 or beat_index >= len(anchors):
        raise IndexError("beat index is outside the reviewed timing map")
    old = anchors[beat_index]
    anchors[beat_index] = ReviewedTimingAnchor(
        beat_index=old.beat_index,
        original_time_seconds=old.original_time_seconds,
        reviewed_time_seconds=old.reviewed_time_seconds if time_seconds is None else float(time_seconds),
        locked=old.locked if locked is None else locked,
    )
    return review.model_copy(update={"anchors": anchors, "human_confirmed": False})


def set_reviewed_beat_time(project_dir: Path, beat_index: int, time_seconds: float) -> ReviewedTiming:
    project, manifest, _tempo = _load_current_inputs(project_dir)
    duration = manifest.source_metadata.duration_seconds
    if time_seconds < 0 or time_seconds > duration + 1e-6:
        raise ValueError("reviewed beat time must be inside the recording duration")
    review = load_reviewed_timing(project, create=True)
    updated = _replace_anchor(review, beat_index, time_seconds=time_seconds)
    save_reviewed_timing(project, updated)
    return updated


def nudge_reviewed_beat(project_dir: Path, beat_index: int, delta_seconds: float) -> ReviewedTiming:
    review = load_reviewed_timing(project_dir, create=True)
    anchor = review.anchors[beat_index]
    return set_reviewed_beat_time(project_dir, beat_index, anchor.reviewed_time_seconds + delta_seconds)


def set_anchor_locked(project_dir: Path, beat_index: int, locked: bool) -> ReviewedTiming:
    review = load_reviewed_timing(project_dir, create=True)
    updated = _replace_anchor(review, beat_index, locked=locked)
    save_reviewed_timing(project_dir, updated)
    return updated


def refit_between_locked_anchors(project_dir: Path, beat_index: int) -> ReviewedTiming:
    review = load_reviewed_timing(project_dir, create=True)
    locked = [anchor.beat_index for anchor in review.anchors if anchor.locked]
    left = max((index for index in locked if index <= beat_index), default=None)
    right = min((index for index in locked if index >= beat_index), default=None)
    if left is None or right is None or left == right:
        raise ValueError("refit requires locked anchors on both sides of the selected beat")

    anchors = list(review.anchors)
    left_time = anchors[left].reviewed_time_seconds
    right_time = anchors[right].reviewed_time_seconds
    span = right - left
    for index in range(left + 1, right):
        fraction = (index - left) / span
        old = anchors[index]
        anchors[index] = ReviewedTimingAnchor(
            beat_index=index,
            original_time_seconds=old.original_time_seconds,
            reviewed_time_seconds=left_time + (right_time - left_time) * fraction,
            locked=old.locked,
        )
    updated = review.model_copy(update={"anchors": anchors, "human_confirmed": False})
    save_reviewed_timing(project_dir, updated)
    return updated


def reviewed_tempo_map(project_dir: Path) -> TempoMap:
    project, _manifest, tempo = _load_current_inputs(project_dir)
    review = load_reviewed_timing(project)
    if len(review.anchors) != len(tempo.beats):
        raise ValueError("reviewed timing beat count no longer matches the raw tempo map")

    beats: list[BeatEvent] = []
    for index, (beat, anchor) in enumerate(zip(tempo.beats, review.anchors)):
        next_time = review.anchors[index + 1].reviewed_time_seconds if index + 1 < len(review.anchors) else None
        bpm = beat.bpm
        if next_time is not None:
            interval = next_time - anchor.reviewed_time_seconds
            if interval <= 0:
                raise ValueError("reviewed timing is not strictly increasing")
            bpm = 60.0 / interval
        beats.append(
            beat.model_copy(
                update={
                    "time": anchor.reviewed_time_seconds,
                    "bpm": bpm,
                    "confidence": 1.0 if anchor.locked else beat.confidence,
                }
            )
        )
    return tempo.model_copy(update={"engine": f"{tempo.engine}+human-review", "beats": beats})


def authoritative_tempo_map_path(project_dir: Path) -> Path:
    """Return the current human-promoted map when valid, otherwise the raw analysis map.

    A promoted file is authoritative only while its review provenance still matches the
    current recording/raw tempo map and its bytes parse to the exact map implied by the
    confirmed review layer. This prevents stale or manually altered reviewed artifacts
    from silently affecting validation/export.
    """
    project = project_dir.expanduser().resolve()
    raw_path = _tempo_path(project)
    promoted_path = project / PROMOTED_MAP_PATH
    review_path = project / REVIEW_PATH
    if not promoted_path.is_file() or not review_path.is_file():
        return raw_path
    review = load_reviewed_timing(project)
    if not review.human_confirmed:
        return raw_path
    promoted = read_tempo_map(promoted_path)
    expected = reviewed_tempo_map(project)
    if promoted != expected:
        raise ValueError("promoted reviewed timing is stale or does not match the confirmed review")
    return promoted_path


def promote_reviewed_timing(project_dir: Path) -> tuple[ReviewedTiming, Path]:
    """Human-confirm the reviewed beat map and materialize its authoritative tempo map.

    A no-edit review is first-class: when the user auditions the detector beat grid and
    decides it is already correct, no reviewed artifact exists yet. Create that artifact
    from the current detector map and allow it to be confirmed without manufacturing an
    arbitrary locked anchor. If beat times were actually changed, retain the locked-anchor
    requirement so edited timing still carries explicit correction evidence.
    """
    project = project_dir.expanduser().resolve()
    review = load_reviewed_timing(project, create=True)
    timing_changed = any(
        anchor.reviewed_time_seconds != anchor.original_time_seconds for anchor in review.anchors
    )
    if timing_changed and not any(anchor.locked for anchor in review.anchors):
        raise ValueError("lock at least one reviewed timing anchor before promoting edited timing")
    promoted = review.model_copy(update={"human_confirmed": True})
    save_reviewed_timing(project, promoted)
    tempo = reviewed_tempo_map(project)
    output = project / PROMOTED_MAP_PATH
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(tempo.model_dump_json(indent=2), encoding="utf-8")
    return promoted, output
