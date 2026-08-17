from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from .accepted_score_timing import AcceptedScoreTimingMap, _build_accepted_score_timing_map_locked
from .score_mapping_review import score_mapping_transaction


REVIEWED_SCORE_TIMING_PATH = Path("analysis") / "reviewed_score_timing.json"


class ReviewedScoreTimingAuthority(BaseModel):
    """Explicitly promoted song-level timing authority from accepted bounded score refits."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    method: Literal["accepted-bounded-score-refit-v1"] = "accepted-bounded-score-refit-v1"
    timing_map: AcceptedScoreTimingMap
    human_confirmed: Literal[True] = True

    def write_json(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2) + "\n", encoding="utf-8")
        return path

    @classmethod
    def read_json(cls, path: Path) -> "ReviewedScoreTimingAuthority":
        return cls.model_validate_json(path.read_text(encoding="utf-8"))


def promote_reviewed_score_timing(
    project_dir: Path,
    *,
    expected_map: AcceptedScoreTimingMap,
) -> Path:
    """Promote the exact accepted score-timing map that a human reviewed.

    This is an explicit authority boundary. The current accepted map is rebuilt while the
    score transaction lock is held and must exactly match the map supplied by the caller.
    No timing is inferred or accepted here; promotion only persists already accepted human
    review evidence as song-level timing authority for later arrangement consumers.
    """

    project = project_dir.expanduser().resolve()
    with score_mapping_transaction(project):
        current = _build_accepted_score_timing_map_locked(project)
        if current != expected_map:
            raise ValueError(
                "accepted score timing changed after review; refresh Song Workspace and review the current map before promotion"
            )
        authority = ReviewedScoreTimingAuthority(timing_map=current)
        return authority.write_json(project / REVIEWED_SCORE_TIMING_PATH)


def _load_current_reviewed_score_timing_locked(project: Path) -> ReviewedScoreTimingAuthority:
    """Load current promoted authority while the caller holds score transaction authority."""

    path = project / REVIEWED_SCORE_TIMING_PATH
    if not path.is_file():
        raise FileNotFoundError(path)
    persisted = ReviewedScoreTimingAuthority.read_json(path)
    current = _build_accepted_score_timing_map_locked(project)
    if persisted.timing_map != current:
        raise ValueError(
            "reviewed score timing authority is stale because current accepted timing evidence changed"
        )
    return persisted


def load_current_reviewed_score_timing(project_dir: Path) -> ReviewedScoreTimingAuthority:
    """Load promoted score timing only when it still matches current accepted evidence."""

    project = project_dir.expanduser().resolve()
    with score_mapping_transaction(project):
        return _load_current_reviewed_score_timing_locked(project)
