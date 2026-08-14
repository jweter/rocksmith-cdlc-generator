from __future__ import annotations

import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

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


@contextmanager
def _exclusive_contract_lock(contract_path: Path) -> Iterator[None]:
    """Hold an OS-backed exclusive lock while a score contract is read and replaced."""

    lock_path = contract_path.with_name(f".{contract_path.name}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+b")
    try:
        if os.name == "nt":
            import msvcrt

            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        try:
            if os.name == "nt":
                import msvcrt

                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


def load_score_for_mapping_review(project: Path) -> ProjectScoreSource:
    """Load a registered score only after verifying its immutable stored bytes."""

    contract_path = _score_contract_path(project)
    score = ProjectScoreSource.read_json(contract_path)
    project_root = contract_path.parents[2]
    relative_stored = Path(score.imported_relative_path)
    if relative_stored.is_absolute():
        raise ValueError("Registered score source path must remain inside the project")
    stored = (project_root / relative_stored).resolve()
    if not stored.is_relative_to(project_root):
        raise ValueError("Registered score source path must remain inside the project")
    if not stored.is_file() or sha256_file(stored) != score.source_sha256:
        raise IOError("Registered score source bytes do not match the project score contract")
    return score


def _replace_contract_atomically(contract_path: Path, score: ProjectScoreSource) -> None:
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=contract_path.parent,
            prefix=f".{contract_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary.write(score.model_dump_json(indent=2))
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_path = Path(temporary.name)
        temporary_path.replace(contract_path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


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
    Concurrent confirmations are serialized so one successful role decision cannot
    overwrite another role's successful decision.
    """

    contract_path = _score_contract_path(project)
    with _exclusive_contract_lock(contract_path):
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
        _replace_contract_atomically(contract_path, updated)
        return confirmed
