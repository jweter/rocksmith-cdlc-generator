from __future__ import annotations

from pathlib import Path

from .hashing import sha256_file
from .score_source import (
    ArrangementRole,
    ProjectScoreSource,
    ScoreArrangementMapping,
)


def _score_contract_path(project: Path) -> Path:
    resolved = project.expanduser().resolve()
    if not (resolved / "project.json").is_file():
        raise FileNotFoundError(f"Not a CDLC project: {resolved}")
    contract_path = resolved / "sources" / "score" / "source.json"
    if not contract_path.is_file():
        raise FileNotFoundError(f"Project has no registered complete score: {contract_path}")
    return contract_path


def load_score_for_mapping_review(project: Path) -> ProjectScoreSource:
    """Load a registered score only after verifying its immutable stored bytes."""

    contract_path = _score_contract_path(project)
    score = ProjectScoreSource.read_json(contract_path)
    project_root = contract_path.parents[2]
    stored = project_root / score.imported_relative_path
    if not stored.is_file() or sha256_file(stored) != score.source_sha256:
        raise IOError("Registered score source bytes do not match the project score contract")
    return score


def confirm_score_mapping(
    project: Path,
    *,
    role: ArrangementRole,
    source_track_index: int,
) -> ScoreArrangementMapping:
    """Persist one explicit human Bass/Lead/Rhythm track selection.

    Importer confidence is preserved when the human confirms the proposed track. If
    the human selects a different known track, importer confidence is not fabricated;
    the replacement mapping records zero proposal confidence plus explicit human basis.
    """

    contract_path = _score_contract_path(project)
    score = load_score_for_mapping_review(project)
    known_indexes = {track.source_track_index for track in score.tracks}
    if source_track_index not in known_indexes:
        raise ValueError(f"Score track {source_track_index} does not exist")

    existing = score.mapping_for(role)
    if existing is not None and existing.source_track_index == source_track_index:
        confirmed = existing.model_copy(update={"human_confirmed": True})
    else:
        confirmed = ScoreArrangementMapping(
            role=role,
            source_track_index=source_track_index,
            confidence=0.0,
            basis=["human selected score track explicitly"],
            human_confirmed=True,
        )

    mappings = [mapping for mapping in score.arrangement_mappings if mapping.role is not role]
    mappings.append(confirmed)
    updated = score.model_copy(update={"arrangement_mappings": mappings})

    temporary = contract_path.with_name(f".{contract_path.name}.tmp")
    temporary.write_text(updated.model_dump_json(indent=2), encoding="utf-8")
    temporary.replace(contract_path)
    return confirmed
