from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .accepted_score_timing import AcceptedScoreTimingPoint
from .hashing import sha256_file
from .reviewed_positions import _resolve_composed_review_entry_locked
from .reviewed_score_timing_authority import _load_current_reviewed_score_timing_locked
from .score_mapping_review import (
    load_score_for_mapping_review,
    score_mapping_transaction,
)
from .score_source import ArrangementRole
from .shared_timeline import _current_fanout, _safe_project_file


class ReviewedArrangementTiming(BaseModel):
    """One arrangement view of the current promoted score-timing authority."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    method: Literal["accepted-bounded-score-refit-v1"] = "accepted-bounded-score-refit-v1"
    role: ArrangementRole
    source_track_index: int = Field(ge=0)
    source_output_json: str
    source_output_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    recording_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    score_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    points: list[AcceptedScoreTimingPoint]
    human_confirmed: Literal[True] = True


def _reviewed_arrangement_timing_locked(project: Path, role: ArrangementRole) -> ReviewedArrangementTiming:
    """Project promoted score timing onto one confirmed arrangement while locked."""

    authority = _load_current_reviewed_score_timing_locked(project)
    timing_map = authority.timing_map
    score = load_score_for_mapping_review(project)
    if score.source_sha256 != timing_map.score_sha256:
        raise ValueError("reviewed score timing does not match the current registered score")

    mapping = score.mapping_for(role)
    if mapping is None or not mapping.human_confirmed:
        raise ValueError(f"{role.value} score mapping is not human-confirmed")

    fanout = _current_fanout(project, score)
    entry = next((item for item in fanout.arrangements if item.role is role), None)
    if entry is None or entry.source_track_index != mapping.source_track_index:
        raise ValueError(f"{role.value} fan-out output is not current")
    entry = _resolve_composed_review_entry_locked(
        project,
        role.value,
        score=score,
        entry=entry,
    )
    output = _safe_project_file(project, entry.output_json)

    return ReviewedArrangementTiming(
        role=role,
        source_track_index=mapping.source_track_index,
        source_output_json=entry.output_json,
        source_output_sha256=sha256_file(output),
        recording_sha256=timing_map.recording_sha256,
        score_sha256=timing_map.score_sha256,
        points=timing_map.points,
        human_confirmed=True,
    )


def reviewed_arrangement_timing(project_dir: Path, role: ArrangementRole) -> ReviewedArrangementTiming:
    """Return the exact promoted score timing inherited by one confirmed arrangement.

    Authority validation, score mapping validation, fan-out validation, and projection are
    serialized under the shared score transaction lock so a remap or fan-out cannot race
    the arrangement view. For a current multi-track Lead/Rhythm composition, this may
    refresh its deterministic project-local composed-source cache; it does not alter
    review, chart, export, package, or timing authority.
    """

    project = project_dir.expanduser().resolve()
    with score_mapping_transaction(project):
        return _reviewed_arrangement_timing_locked(project, role)
