from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from .score_mapping_review import score_mapping_transaction
from .score_timing_anchors import ScoreTimingRefitPreview, build_score_timing_refit_preview
from .shared_timeline import SharedTimeline, build_shared_timeline_candidate


REFIT_ACCEPTANCE_PATH = Path("review") / "score_timing_refit_acceptance.json"


class ScoreTimingRefitAcceptance(BaseModel):
    """Exact human acceptance evidence for one bounded score-timing refit preview."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    candidate: SharedTimeline
    preview: ScoreTimingRefitPreview
    human_confirmed: Literal[True] = True

    def write_json(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return path

    @classmethod
    def read_json(cls, path: Path) -> "ScoreTimingRefitAcceptance":
        return cls.model_validate_json(path.read_text(encoding="utf-8"))


def acceptance_for(
    candidate: SharedTimeline,
    preview: ScoreTimingRefitPreview,
) -> ScoreTimingRefitAcceptance:
    """Create acceptance evidence only when candidate and preview provenance agree."""
    if preview.recording_sha256 != candidate.recording_sha256:
        raise ValueError("bounded timing refit preview recording does not match the reviewed candidate")
    if preview.score_sha256 != candidate.score_sha256:
        raise ValueError("bounded timing refit preview score does not match the reviewed candidate")
    if preview.authority_track_index != candidate.authority_track_index:
        raise ValueError("bounded timing refit preview authority track does not match the reviewed candidate")
    if preview.authority_output_sha256 != candidate.authority_output_sha256:
        raise ValueError("bounded timing refit preview authority output does not match the reviewed candidate")
    return ScoreTimingRefitAcceptance(candidate=candidate, preview=preview)


def require_current_acceptance(
    acceptance: ScoreTimingRefitAcceptance,
    candidate: SharedTimeline,
    preview: ScoreTimingRefitPreview,
) -> ScoreTimingRefitAcceptance:
    """Fail closed unless persisted human evidence matches the exact current proposal."""
    current = acceptance_for(candidate, preview)
    if acceptance != current:
        raise ValueError(
            "bounded timing refit acceptance is stale because the reviewed candidate or refit preview changed"
        )
    return acceptance


def accept_score_timing_refit(
    project_dir: Path,
    *,
    expected_candidate: SharedTimeline,
    expected_preview: ScoreTimingRefitPreview,
) -> Path:
    """Persist explicit acceptance of the exact candidate/refit preview shown to the user.

    This is review evidence only. It never writes analysis/shared_timeline.json and never
    makes the refit authoritative by itself.
    """
    project = project_dir.expanduser().resolve()
    with score_mapping_transaction(project):
        candidate = build_shared_timeline_candidate(project)
        if candidate != expected_candidate:
            raise ValueError(
                "shared timing candidate changed after refit review; refresh Song Workspace and review again"
            )
        preview = build_score_timing_refit_preview(project, expected_candidate=candidate)
        if preview != expected_preview:
            raise ValueError(
                "bounded timing refit preview changed after review; refresh Song Workspace and review again"
            )
        acceptance = acceptance_for(candidate, preview)
        return acceptance.write_json(project / REFIT_ACCEPTANCE_PATH)


def load_current_score_timing_refit_acceptance(project_dir: Path) -> ScoreTimingRefitAcceptance:
    """Load persisted refit acceptance only when it still matches current project authority."""
    project = project_dir.expanduser().resolve()
    path = project / REFIT_ACCEPTANCE_PATH
    if not path.is_file():
        raise FileNotFoundError(path)
    acceptance = ScoreTimingRefitAcceptance.read_json(path)
    candidate = build_shared_timeline_candidate(project)
    preview = build_score_timing_refit_preview(project, expected_candidate=candidate)
    return require_current_acceptance(acceptance, candidate, preview)
