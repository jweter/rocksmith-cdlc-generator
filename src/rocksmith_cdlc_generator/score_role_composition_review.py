from __future__ import annotations

import os
import tempfile
from pathlib import Path

from .score_mapping_review import load_score_for_mapping_review, score_mapping_transaction
from .score_role_composition import (
    ScoreRoleCompositionPlan,
    build_score_role_composition_plan,
    validate_score_role_composition,
)
from .score_source import ArrangementRole

SCORE_ROLE_COMPOSITION_PATH = Path("review") / "score_role_composition.json"


def _project(project_dir: Path) -> Path:
    project = project_dir.expanduser().resolve()
    if not (project / "project.json").is_file():
        raise FileNotFoundError(f"Not a CDLC project: {project}")
    return project


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary.write(text)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_path = Path(temporary.name)
        temporary_path.replace(path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def load_current_score_role_composition(project_dir: Path) -> ScoreRoleCompositionPlan | None:
    """Load persisted composition intent and fail closed if its authority is stale."""

    project = _project(project_dir)
    with score_mapping_transaction(project):
        path = project / SCORE_ROLE_COMPOSITION_PATH
        if not path.is_file():
            return None
        score = load_score_for_mapping_review(project)
        plan = ScoreRoleCompositionPlan.model_validate_json(path.read_text(encoding="utf-8"))
        return validate_score_role_composition(score, plan)


def record_score_role_composition(
    project_dir: Path,
    *,
    selections: dict[ArrangementRole, list[int]],
) -> ScoreRoleCompositionPlan:
    """Persist one explicit ordered composition plan for the current score authority.

    The write is serialized with score mapping/fan-out operations and fully revalidates
    the current registered score and confirmed primary mappings. It grants no authority
    over note conflicts, timing, fingering, techniques, chords, tones, or export.
    """

    project = _project(project_dir)
    with score_mapping_transaction(project):
        score = load_score_for_mapping_review(project)
        plan = build_score_role_composition_plan(score, selections)
        _atomic_write(
            project / SCORE_ROLE_COMPOSITION_PATH,
            plan.model_dump_json(indent=2) + "\n",
        )
        return plan
