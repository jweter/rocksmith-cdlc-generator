from __future__ import annotations

from bisect import bisect_right
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from .models import ProjectManifest
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

    schema_version: Literal[2] = 2
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


def nearest_candidate_anchor(candidate: SharedTimeline, recording_time_seconds: float):
    """Return the proposed score anchor nearest a recording timestamp."""
    if not candidate.anchors:
        return None
    when = float(recording_time_seconds)
    return min(
        candidate.anchors,
        key=lambda item: (abs(item.audio_time_seconds - when), item.audio_time_seconds, item.source_beat_index),
    )


def _require_expected_candidate(candidate: SharedTimeline, expected_candidate: SharedTimeline | None) -> None:
    if expected_candidate is not None and candidate != expected_candidate:
        raise ValueError(
            "score timing candidate changed after it was shown for review; refresh Song Workspace and review the current candidate"
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
    return ScoreTimingAnchorReview(
        recording_sha256=review.recording_sha256,
        score_sha256=review.score_sha256,
        authority_track_index=review.authority_track_index,
        authority_output_sha256=review.authority_output_sha256,
        anchors=anchors,
    )


def _candidate_time_for_source_beat(
    candidate: SharedTimeline,
    imported: ImportedSource,
    source_beat_index: int,
) -> float:
    if source_beat_index < 0 or source_beat_index >= len(imported.beat_times_seconds):
        raise IndexError("score beat is outside the current authority beat grid")
    if len(candidate.anchors) < 2:
        raise ValueError("current timing candidate does not contain enough anchors to map a score beat")

    source_time = imported.beat_times_seconds[source_beat_index]
    anchors = candidate.anchors
    if source_time <= anchors[0].source_time_seconds:
        first, second = anchors[0], anchors[1]
    elif source_time >= anchors[-1].source_time_seconds:
        first, second = anchors[-2], anchors[-1]
    else:
        source_times = [item.source_time_seconds for item in anchors]
        right = bisect_right(source_times, source_time)
        first, second = anchors[right - 1], anchors[right]

    span = second.source_time_seconds - first.source_time_seconds
    if span <= 0:
        raise ValueError("current timing candidate source anchors are not strictly increasing")
    fraction = (source_time - first.source_time_seconds) / span
    return first.audio_time_seconds + fraction * (second.audio_time_seconds - first.audio_time_seconds)


def _validate_recording_time(recording_time_seconds: float, duration_seconds: float) -> float:
    value = float(recording_time_seconds)
    if value < 0 or value > duration_seconds + 1e-6:
        raise ValueError("recording time must be inside the current recording duration")
    return value


def _load_persisted_review(path: Path, candidate: SharedTimeline) -> ScoreTimingAnchorReview:
    text = path.read_text(encoding="utf-8")
    try:
        return ScoreTimingAnchorReview.model_validate_json(text)
    except ValidationError:
        try:
            raw = json.loads(text)
        except (TypeError, ValueError):
            raise
        if isinstance(raw, dict) and raw.get("schema_version") == 1:
            # Version 1 may contain evidence created before the duration and exact
            # candidate-time integrity rules. Discard it rather than reuse or migrate it.
            # Returning a fresh v2 review lets normal product actions re-review safely.
            return review_for_candidate(candidate)
        raise


def _load_review_for_candidate(project: Path, candidate: SharedTimeline) -> ScoreTimingAnchorReview:
    path = project / ANCHOR_REVIEW_PATH
    if not path.is_file():
        return review_for_candidate(candidate)
    review = _load_persisted_review(path, candidate)
    expected = review_for_candidate(candidate, anchors=review.anchors)
    if review != expected:
        # Current-schema evidence bound to a prior recording/score/authority is not
        # applicable to the new candidate. Discard it in memory and let the next
        # explicit human anchor action replace the stale generated review artifact.
        return review_for_candidate(candidate)
    return review


def load_score_timing_anchor_review(project_dir: Path) -> ScoreTimingAnchorReview:
    project = project_dir.expanduser().resolve()
    candidate = build_shared_timeline_candidate(project)
    return _load_review_for_candidate(project, candidate)


def save_score_timing_anchor_review(project_dir: Path, review: ScoreTimingAnchorReview) -> Path:
    project = project_dir.expanduser().resolve()
    path = project / ANCHOR_REVIEW_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(review.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path


def confirm_candidate_anchor(
    project_dir: Path,
    source_beat_index: int,
    *,
    expected_candidate: SharedTimeline | None = None,
) -> ScoreTimingAnchorReview:
    project = project_dir.expanduser().resolve()
    candidate = build_shared_timeline_candidate(project)
    _require_expected_candidate(candidate, expected_candidate)
    matched = next((anchor for anchor in candidate.anchors if anchor.source_beat_index == source_beat_index), None)
    if matched is None:
        raise ValueError("selected score beat is not one of the current proposed alignment anchors")
    review = _load_review_for_candidate(project, candidate)
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
    *,
    expected_candidate: SharedTimeline | None = None,
) -> ScoreTimingAnchorReview:
    project = project_dir.expanduser().resolve()
    candidate = build_shared_timeline_candidate(project)
    _require_expected_candidate(candidate, expected_candidate)
    imported = _authority_source(project, candidate)
    if source_beat_index < 0 or source_beat_index >= len(imported.beat_times_seconds):
        raise IndexError("score beat is outside the current authority beat grid")

    manifest = ProjectManifest.load(project)
    reviewed_time = _validate_recording_time(
        recording_time_seconds,
        manifest.source_metadata.duration_seconds,
    )
    candidate_time = _candidate_time_for_source_beat(candidate, imported, source_beat_index)
    review = _load_review_for_candidate(project, candidate)
    updated = _upsert(
        review,
        ScoreTimingAnchor(
            source_beat_index=source_beat_index,
            recording_time_seconds=reviewed_time,
            origin="manual_cursor",
            candidate_time_seconds=candidate_time,
        ),
    )
    save_score_timing_anchor_review(project, updated)
    return updated
