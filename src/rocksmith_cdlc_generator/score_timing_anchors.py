from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .shared_timeline import SharedTimeline, build_shared_timeline_candidate
from .source_import import ImportedSource


ANCHOR_REVIEW_PATH = Path("review") / "score_timing_anchors.json"


class ScoreTimingAnchor(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_beat_index: int = Field(ge=0)
    recording_time_seconds: float = Field(ge=0)
    origin: Literal["confirmed_candidate", "manual_cursor"]
    candidate_time_seconds: float | None = Field(default=None, ge=0)


class ScoreTimingAnchorReview(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    recording_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    score_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    authority_track_index: int = Field(ge=0)
    authority_output_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    anchors: list[ScoreTimingAnchor] = Field(default_factory=list)

    @model_validator(mode="after")
    def anchors_are_ordered(self) -> "ScoreTimingAnchorReview":
        indices = [anchor.source_beat_index for anchor in self.anchors]
        if indices != sorted(indices) or len(indices) != len(set(indices)):
            raise ValueError("score timing anchors must have unique ascending source beat indices")
        times = [anchor.recording_time_seconds for anchor in self.anchors]
        if any(current <= previous for previous, current in zip(times, times[1:])):
            raise ValueError("score timing anchors must remain strictly increasing in recording time")
        return self


def review_for_candidate(candidate: SharedTimeline, anchors: list[ScoreTimingAnchor] | None = None) -> ScoreTimingAnchorReview:
    return ScoreTimingAnchorReview(
        recording_sha256=candidate.recording_sha256,
        score_sha256=candidate.score_sha256,
        authority_track_index=candidate.authority_track_index,
        authority_output_sha256=candidate.authority_output_sha256,
        anchors=[] if anchors is None else anchors,
    )


def _authority_source(project: Path, candidate: SharedTimeline) -> ImportedSource:
    output = (project / candidate.authority_output_json).resolve()
    if not output.is_relative_to(project) or not output.is_file():
        raise ValueError("score timing anchor authority output is not a current project file")
    imported = ImportedSource.read_json(output)
    if not imported.beat_times_seconds:
        raise ValueError("score timing anchor authority has no symbolic beat grid")
    return imported


def _upsert(review: ScoreTimingAnchorReview, anchor: ScoreTimingAnchor) -> ScoreTimingAnchorReview:
    anchors = [item for item in review.anchors if item.source_beat_index != anchor.source_beat_index]
    anchors.append(anchor)
    anchors.sort(key=lambda item: item.source_beat_index)
    return review.model_copy(update={"anchors": anchors})


def load_score_timing_anchor_review(project_dir: Path) -> ScoreTimingAnchorReview:
    project = project_dir.expanduser().resolve()
    candidate = build_shared_timeline_candidate(project)
    path = project / ANCHOR_REVIEW_PATH
    if not path.is_file():
        return review_for_candidate(candidate)
    review = ScoreTimingAnchorReview.model_validate_json(path.read_text(encoding="utf-8"))
    expected = review_for_candidate(candidate, anchors=review.anchors)
    if review != expected:
        raise ValueError("score timing anchors are stale because the reviewed timing candidate changed")
    return review


def save_score_timing_anchor_review(project_dir: Path, review: ScoreTimingAnchorReview) -> Path:
    project = project_dir.expanduser().resolve()
    path = project / ANCHOR_REVIEW_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(review.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path


def confirm_candidate_anchor(project_dir: Path, source_beat_index: int) -> ScoreTimingAnchorReview:
    project = project_dir.expanduser().resolve()
    candidate = build_shared_timeline_candidate(project)
    matched = next((anchor for anchor in candidate.anchors if anchor.source_beat_index == source_beat_index), None)
    if matched is None:
        raise ValueError("selected score beat is not one of the current proposed alignment anchors")
    review = load_score_timing_anchor_review(project)
    updated = _upsert(
        review,
        ScoreTimingAnchor(
            source_beat_index=source_beat_index,
            recording_time_seconds=matched.audio_time_seconds,
            origin="confirmed_candidate",
            candidate_time_seconds=matched.audio_time_seconds,
        ),
    )
    save_score_timing_anchor_review(project, updated)
    return updated


def mark_score_beat_at_recording_time(
    project_dir: Path,
    source_beat_index: int,
    recording_time_seconds: float,
) -> ScoreTimingAnchorReview:
    project = project_dir.expanduser().resolve()
    candidate = build_shared_timeline_candidate(project)
    imported = _authority_source(project, candidate)
    if source_beat_index < 0 or source_beat_index >= len(imported.beat_times_seconds):
        raise IndexError("score beat is outside the current authority beat grid")
    if recording_time_seconds < 0:
        raise ValueError("recording time must be non-negative")
    nearest = min(candidate.anchors, key=lambda item: abs(item.source_beat_index - source_beat_index)) if candidate.anchors else None
    review = load_score_timing_anchor_review(project)
    updated = _upsert(
        review,
        ScoreTimingAnchor(
            source_beat_index=source_beat_index,
            recording_time_seconds=float(recording_time_seconds),
            origin="manual_cursor",
            candidate_time_seconds=None if nearest is None else nearest.audio_time_seconds,
        ),
    )
    save_score_timing_anchor_review(project, updated)
    return updated
