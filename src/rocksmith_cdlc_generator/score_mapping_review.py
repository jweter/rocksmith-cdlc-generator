from __future__ import annotations

import errno
import os
import shutil
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .hashing import sha256_file
from .score_source import (
    ArrangementRole,
    ProjectScoreSource,
    ScoreArrangementMapping,
)

_WINDOWS_LOCK_RETRY_ERRNOS = {errno.EACCES, errno.EAGAIN, errno.EDEADLK}
_WINDOWS_LOCK_RETRY_SECONDS = 0.1


def _score_contract_path(project: Path) -> Path:
    resolved = project.expanduser().resolve()
    if not (resolved / "project.json").is_file():
        raise FileNotFoundError(f"Not a CDLC project: {resolved}")
    contract_path = resolved / "sources" / "score" / "source.json"
    if not contract_path.is_file():
        raise FileNotFoundError(f"Project has no registered complete score: {contract_path}")
    return contract_path


def _lock_windows_byte(handle: Any, msvcrt: Any) -> None:
    """Wait until the one-byte Windows transaction lock becomes available.

    ``msvcrt.LK_LOCK`` has a finite built-in retry window. Fan-out can legitimately
    hold the project transaction longer than that, so use the non-blocking primitive
    and retry only lock-contention errors until the current transaction completes.
    Non-contention OS errors still surface immediately rather than spinning forever.
    """

    while True:
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            return
        except OSError as exc:
            if exc.errno not in _WINDOWS_LOCK_RETRY_ERRNOS:
                raise
            time.sleep(_WINDOWS_LOCK_RETRY_SECONDS)


@contextmanager
def _exclusive_contract_lock(contract_path: Path) -> Iterator[None]:
    """Hold an OS-backed exclusive lock while a score transaction is active."""

    lock_path = contract_path.with_name(f".{contract_path.name}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+b")
    acquired = False
    try:
        if os.name == "nt":
            import msvcrt

            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"\0")
                handle.flush()
            _lock_windows_byte(handle, msvcrt)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        acquired = True
        yield
    finally:
        try:
            if acquired:
                if os.name == "nt":
                    import msvcrt

                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


@contextmanager
def score_mapping_transaction(project: Path) -> Iterator[Path]:
    """Serialize operations that depend on the human-confirmed score contract.

    Mapping confirmation and arrangement fan-out share this transaction lock so an
    authority manifest can never be published concurrently with a mapping change.
    The yielded path is the verified project-local score contract path.
    """

    contract_path = _score_contract_path(project)
    with _exclusive_contract_lock(contract_path):
        yield contract_path


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
    original_stat = contract_path.stat()
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

        # Preserve shared-project access before the atomic replacement. On POSIX,
        # changing group ownership can clear special mode bits, so copy the mode last.
        if os.name != "nt":
            os.chown(temporary_path, -1, original_stat.st_gid)
        shutil.copymode(contract_path, temporary_path)
        temporary_path.replace(contract_path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _invalidate_score_fanout_manifest(contract_path: Path, score: ProjectScoreSource) -> None:
    project_root = contract_path.parents[2]
    manifest = (
        project_root
        / "sources"
        / "imported"
        / f"score-fanout-{score.source_sha256[:12]}.json"
    )
    manifest.unlink(missing_ok=True)


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
    overwrite another role's successful decision. A real mapping change invalidates
    any existing fan-out authority manifest; repeating an already-confirmed mapping is
    a true no-op and preserves the still-valid manifest.
    """

    with score_mapping_transaction(project) as contract_path:
        score = load_score_for_mapping_review(project)
        known_indexes = {track.source_track_index for track in score.tracks}
        if source_track_index not in known_indexes:
            raise ValueError(f"Score track {source_track_index} does not exist")

        existing = score.mapping_for(role)
        if (
            existing is not None
            and existing.source_track_index == source_track_index
            and existing.human_confirmed
        ):
            return existing

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

        # A published fan-out manifest describes the previous confirmed mapping set.
        # Remove that authority marker before changing the mapping contract so a stale
        # manifest can never survive a successful remap.
        _invalidate_score_fanout_manifest(contract_path, score)
        _replace_contract_atomically(contract_path, updated)
        return confirmed
