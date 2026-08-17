from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .score_mapping_review import score_mapping_transaction
from .score_timing_anchors import _authority_source, _candidate_time_for_source_beat
from .score_timing_refit_review import load_current_score_timing_refit_acceptance


class AcceptedScoreTimingPoint(BaseModel):
    """One symbolic score beat after applying only explicitly accepted bounded refits."""

    model_config = ConfigDict(frozen=True)

    source_beat_index: int = Field(ge=0)
    source_time_seconds: float = Field(ge=0)
    candidate_time_seconds: float = Field(ge=0)
    reviewed_time_seconds: float = Field(ge=0)
    review_origin: Literal["candidate", "bounded_refit", "human_anchor"]


class AcceptedScoreTimingMap(BaseModel):
    """Read-only song-wide beat map derived from current accepted score-timing evidence.

    Human refit interpolation applies only inside accepted neighboring-anchor bounds.
    Every score beat outside those bounds retains the current automatic candidate time.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    recording_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    score_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    authority_track_index: int = Field(ge=0)
    authority_output_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    human_anchor_count: int = Field(ge=2)
    bounded_region_count: int = Field(ge=1)
    reviewed_beat_count: int = Field(ge=2)
    unchanged_beat_count: int = Field(ge=0)
    max_abs_adjustment_seconds: float = Field(ge=0)
    points: list[AcceptedScoreTimingPoint]

    @model_validator(mode="after")
    def points_are_complete_and_monotonic(self) -> "AcceptedScoreTimingMap":
        if not self.points:
            raise ValueError("accepted score timing map must contain score beats")
        indices = [point.source_beat_index for point in self.points]
        if indices != list(range(len(self.points))):
            raise ValueError("accepted score timing map must cover the complete authority score beat grid")
        source_times = [point.source_time_seconds for point in self.points]
        if any(current <= previous for previous, current in zip(source_times, source_times[1:])):
            raise ValueError("accepted score timing source beats must remain strictly increasing")
        reviewed_times = [point.reviewed_time_seconds for point in self.points]
        if any(current <= previous for previous, current in zip(reviewed_times, reviewed_times[1:])):
            raise ValueError(
                "accepted score timing would reverse or collapse neighboring recording beats; add or correct human anchors before promotion"
            )
        reviewed = sum(point.review_origin != "candidate" for point in self.points)
        unchanged = sum(point.review_origin == "candidate" for point in self.points)
        if reviewed != self.reviewed_beat_count or unchanged != self.unchanged_beat_count:
            raise ValueError("accepted score timing review counts do not match materialized points")
        return self


def _build_accepted_score_timing_map_locked(project: Path) -> AcceptedScoreTimingMap:
    """Materialize the current accepted map while the caller holds score transaction authority."""
    acceptance = load_current_score_timing_refit_acceptance(project)
    candidate = acceptance.candidate
    preview = acceptance.preview
    imported = _authority_source(project, candidate)

    refit_points = {}
    for region in preview.regions:
        for point in region.points:
            existing = refit_points.get(point.source_beat_index)
            if existing is not None and existing != point:
                raise ValueError("accepted bounded refit contains conflicting values for one score beat")
            refit_points[point.source_beat_index] = point

    points: list[AcceptedScoreTimingPoint] = []
    max_adjustment = 0.0
    for beat_index, source_time in enumerate(imported.beat_times_seconds):
        candidate_time = _candidate_time_for_source_beat(candidate, imported, beat_index)
        refit = refit_points.get(beat_index)
        if refit is None:
            reviewed_time = candidate_time
            origin: Literal["candidate", "bounded_refit", "human_anchor"] = "candidate"
        else:
            reviewed_time = refit.refit_time_seconds
            origin = "human_anchor" if refit.human_anchor else "bounded_refit"
        max_adjustment = max(max_adjustment, abs(reviewed_time - candidate_time))
        points.append(
            AcceptedScoreTimingPoint(
                source_beat_index=beat_index,
                source_time_seconds=source_time,
                candidate_time_seconds=candidate_time,
                reviewed_time_seconds=reviewed_time,
                review_origin=origin,
            )
        )

    reviewed_count = sum(point.review_origin != "candidate" for point in points)
    return AcceptedScoreTimingMap(
        recording_sha256=candidate.recording_sha256,
        score_sha256=candidate.score_sha256,
        authority_track_index=candidate.authority_track_index,
        authority_output_sha256=candidate.authority_output_sha256,
        human_anchor_count=preview.human_anchor_count,
        bounded_region_count=len(preview.regions),
        reviewed_beat_count=reviewed_count,
        unchanged_beat_count=len(points) - reviewed_count,
        max_abs_adjustment_seconds=max_adjustment,
        points=points,
    )


def build_accepted_score_timing_map(project_dir: Path) -> AcceptedScoreTimingMap:
    """Materialize current human-accepted bounded refits without promoting timing.

    Acceptance validation, authority loading, and complete map construction share the
    score-mapping transaction lock. This prevents concurrent score fan-out from replacing
    the role-based authority output after its accepted provenance was validated but before
    its symbolic beat grid is materialized.

    Human interpolation is used only for score beats present in the accepted bounded-refit
    preview; all beats before, after, or between unreviewed bounds keep the current
    automatic candidate mapping.
    """

    project = project_dir.expanduser().resolve()
    with score_mapping_transaction(project):
        return _build_accepted_score_timing_map_locked(project)
