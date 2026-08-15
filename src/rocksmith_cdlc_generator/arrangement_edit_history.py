from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .hashing import sha256_file
from .score_fanout import ScoreFanoutManifest
from .score_mapping_review import load_score_for_mapping_review

EditKind = Literal[
    "position",
    "chord_fingering",
    "event_timing",
    "techniques",
    "chord_identity",
]

HISTORY_PATH = Path("review") / "arrangement_edit_history.json"
_SHARED_TIMELINE_PATH = Path("analysis") / "shared_timeline.json"


def _text_sha256(content: str) -> str:
    return sha256(content.encode("utf-8")).hexdigest()


class ReviewFileSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: str
    content: str | None = None
    content_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_snapshot(self) -> "ReviewFileSnapshot":
        pure = PurePosixPath(self.path)
        if pure.is_absolute() or not self.path or ".." in pure.parts:
            raise ValueError("history snapshot path must be project-relative and cannot escape the project")
        if self.content is None:
            if self.content_sha256 is not None:
                raise ValueError("absent history snapshot cannot carry a content hash")
        elif self.content_sha256 != _text_sha256(self.content):
            raise ValueError("history snapshot content hash does not match stored content")
        return self


class ArrangementEditTransaction(BaseModel):
    model_config = ConfigDict(frozen=True)

    transaction_id: str
    kind: EditKind
    created_at: datetime
    score_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    score_format: str
    fanout_manifest_path: str
    fanout_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    shared_timeline_path: str | None = None
    shared_timeline_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    before: list[ReviewFileSnapshot] = Field(min_length=1)
    after: list[ReviewFileSnapshot] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_transaction(self) -> "ArrangementEditTransaction":
        before_paths = [item.path for item in self.before]
        after_paths = [item.path for item in self.after]
        if len(before_paths) != len(set(before_paths)) or len(after_paths) != len(set(after_paths)):
            raise ValueError("history transaction contains duplicate snapshot paths")
        if before_paths != after_paths:
            raise ValueError("history transaction before/after paths must match in stable order")
        timing_values = (self.shared_timeline_path, self.shared_timeline_sha256)
        if (timing_values[0] is None) != (timing_values[1] is None):
            raise ValueError("history timing provenance must include both path and SHA-256")
        return self


class ArrangementEditHistory(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    transactions: list[ArrangementEditTransaction] = Field(default_factory=list)
    cursor: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def cursor_is_valid(self) -> "ArrangementEditHistory":
        if self.cursor > len(self.transactions):
            raise ValueError("arrangement edit history cursor is beyond the transaction list")
        ids = [item.transaction_id for item in self.transactions]
        if len(ids) != len(set(ids)):
            raise ValueError("arrangement edit history contains duplicate transaction IDs")
        return self

    @property
    def can_undo(self) -> bool:
        return self.cursor > 0

    @property
    def can_redo(self) -> bool:
        return self.cursor < len(self.transactions)


def _safe_project_path(project: Path, relative: str | Path) -> Path:
    raw = Path(relative)
    if raw.is_absolute():
        raise ValueError("history-managed review path must be project-relative")
    resolved = (project / raw).resolve()
    if not resolved.is_relative_to(project):
        raise ValueError("history-managed review path escaped the project directory")
    if resolved == project / HISTORY_PATH:
        raise ValueError("arrangement history cannot snapshot its own history file")
    return resolved


def _current_authority(project: Path, *, timing_bound: bool) -> dict[str, str | None]:
    score = load_score_for_mapping_review(project)
    fanout_path = project / "sources" / "imported" / f"score-fanout-{score.source_sha256[:12]}.json"
    if not fanout_path.is_file():
        raise FileNotFoundError("Current score fan-out manifest is not available")
    manifest = ScoreFanoutManifest.model_validate_json(fanout_path.read_text(encoding="utf-8"))
    if manifest.score_source_sha256 != score.source_sha256 or manifest.score_source_format != score.source_format:
        raise ValueError("Current score fan-out does not match the registered score")
    result: dict[str, str | None] = {
        "score_sha256": score.source_sha256,
        "score_format": score.source_format,
        "fanout_manifest_path": fanout_path.relative_to(project).as_posix(),
        "fanout_manifest_sha256": sha256_file(fanout_path),
        "shared_timeline_path": None,
        "shared_timeline_sha256": None,
    }
    if timing_bound:
        timeline_path = project / _SHARED_TIMELINE_PATH
        if not timeline_path.is_file():
            raise FileNotFoundError("Current shared timing authority is not available")
        result["shared_timeline_path"] = timeline_path.relative_to(project).as_posix()
        result["shared_timeline_sha256"] = sha256_file(timeline_path)
    return result


def _transaction_matches_current_authority(project: Path, transaction: ArrangementEditTransaction) -> bool:
    current = _current_authority(project, timing_bound=transaction.shared_timeline_path is not None)
    return (
        transaction.score_sha256 == current["score_sha256"]
        and transaction.score_format == current["score_format"]
        and transaction.fanout_manifest_path == current["fanout_manifest_path"]
        and transaction.fanout_manifest_sha256 == current["fanout_manifest_sha256"]
        and transaction.shared_timeline_path == current["shared_timeline_path"]
        and transaction.shared_timeline_sha256 == current["shared_timeline_sha256"]
    )


def _history_matches_current_authority(project: Path, history: ArrangementEditHistory) -> bool:
    try:
        return all(
            _transaction_matches_current_authority(project, item)
            for item in history.transactions
        )
    except (OSError, ValueError):
        return False


def _read_history_unchecked(project: Path) -> ArrangementEditHistory:
    path = project / HISTORY_PATH
    if not path.is_file():
        return ArrangementEditHistory()
    return ArrangementEditHistory.model_validate_json(path.read_text(encoding="utf-8"))


def load_current_arrangement_edit_history(project_dir: Path) -> ArrangementEditHistory:
    project = project_dir.expanduser().resolve()
    history = _read_history_unchecked(project)
    if not _history_matches_current_authority(project, history):
        raise ValueError("Arrangement edit history is stale for the current score/fan-out/timing authority")
    return history


def _snapshot(project: Path, relative: str | Path, *, content: str | None | object = ...) -> ReviewFileSnapshot:
    path = _safe_project_path(project, relative)
    relative_text = path.relative_to(project).as_posix()
    if content is ...:
        actual = path.read_text(encoding="utf-8") if path.is_file() else None
    else:
        actual = content
    if actual is not None and not isinstance(actual, str):
        raise TypeError("history snapshot content must be text or None")
    return ReviewFileSnapshot(
        path=relative_text,
        content=actual,
        content_sha256=None if actual is None else _text_sha256(actual),
    )


def _snapshot_matches_disk(project: Path, snapshot: ReviewFileSnapshot) -> bool:
    path = _safe_project_path(project, snapshot.path)
    if snapshot.content is None:
        return not path.exists()
    if not path.is_file():
        return False
    return path.read_text(encoding="utf-8") == snapshot.content


def _write_snapshot(project: Path, snapshot: ReviewFileSnapshot) -> None:
    path = _safe_project_path(project, snapshot.path)
    if snapshot.content is None:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".history.tmp")
    temporary.write_text(snapshot.content, encoding="utf-8")
    temporary.replace(path)


def _apply_snapshots(project: Path, snapshots: list[ReviewFileSnapshot]) -> None:
    originals = [_snapshot(project, item.path) for item in snapshots]
    applied = 0
    try:
        for snapshot in snapshots:
            _write_snapshot(project, snapshot)
            applied += 1
    except Exception:
        for original in reversed(originals[:applied]):
            _write_snapshot(project, original)
        raise


def _write_history(project: Path, history: ArrangementEditHistory) -> None:
    path = project / HISTORY_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(history.model_dump_json(indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def record_arrangement_review_edit(
    project_dir: Path,
    *,
    kind: EditKind,
    writes: dict[str | Path, str | None],
    timing_bound: bool = False,
    score_sha256: str | None = None,
    score_format: str | None = None,
    fanout_manifest_path: str | None = None,
    fanout_manifest_sha256: str | None = None,
    shared_timeline_path: str | None = None,
    shared_timeline_sha256: str | None = None,
) -> ArrangementEditTransaction:
    """Apply accepted review-layer bytes and append one reversible transaction.

    Callers that just validated an accepted review layer may pass that exact provenance
    instead of reopening the same authority files. Undo/redo always revalidate against
    current project authority independently.
    """

    if not writes:
        raise ValueError("arrangement edit transaction requires at least one review-layer write")
    project = project_dir.expanduser().resolve()
    history = _read_history_unchecked(project)
    if not _history_matches_current_authority(project, history):
        history = ArrangementEditHistory()

    supplied = (score_sha256, score_format, fanout_manifest_path, fanout_manifest_sha256)
    if all(item is None for item in supplied):
        authority = _current_authority(project, timing_bound=timing_bound)
    elif any(item is None for item in supplied):
        raise ValueError("recorded edit provenance must include score and fan-out identity together")
    else:
        if timing_bound and (shared_timeline_path is None or shared_timeline_sha256 is None):
            raise ValueError("timing-bound edit provenance requires shared timeline identity")
        if not timing_bound and (shared_timeline_path is not None or shared_timeline_sha256 is not None):
            raise ValueError("non-timing edit cannot carry shared timeline provenance")
        authority = {
            "score_sha256": score_sha256,
            "score_format": score_format,
            "fanout_manifest_path": fanout_manifest_path,
            "fanout_manifest_sha256": fanout_manifest_sha256,
            "shared_timeline_path": shared_timeline_path,
            "shared_timeline_sha256": shared_timeline_sha256,
        }

    ordered = sorted(writes.items(), key=lambda item: Path(item[0]).as_posix())
    before = [_snapshot(project, relative) for relative, _content in ordered]
    after = [_snapshot(project, relative, content=content) for relative, content in ordered]
    transaction = ArrangementEditTransaction(
        transaction_id=str(uuid4()),
        kind=kind,
        created_at=datetime.now(timezone.utc),
        score_sha256=str(authority["score_sha256"]),
        score_format=str(authority["score_format"]),
        fanout_manifest_path=str(authority["fanout_manifest_path"]),
        fanout_manifest_sha256=str(authority["fanout_manifest_sha256"]),
        shared_timeline_path=authority["shared_timeline_path"],
        shared_timeline_sha256=authority["shared_timeline_sha256"],
        before=before,
        after=after,
    )
    retained = list(history.transactions[: history.cursor])
    retained.append(transaction)
    updated = ArrangementEditHistory(transactions=retained, cursor=len(retained))

    _apply_snapshots(project, after)
    try:
        _write_history(project, updated)
    except Exception:
        _apply_snapshots(project, before)
        raise
    return transaction


def undo_arrangement_edit(project_dir: Path) -> ArrangementEditTransaction:
    project = project_dir.expanduser().resolve()
    history = load_current_arrangement_edit_history(project)
    if not history.can_undo:
        raise ValueError("No accepted arrangement edit is available to undo")
    transaction = history.transactions[history.cursor - 1]
    if not all(_snapshot_matches_disk(project, item) for item in transaction.after):
        raise ValueError("Cannot undo because a managed review layer changed outside arrangement edit history")
    _apply_snapshots(project, transaction.before)
    updated = history.model_copy(update={"cursor": history.cursor - 1})
    try:
        _write_history(project, updated)
    except Exception:
        _apply_snapshots(project, transaction.after)
        raise
    return transaction


def redo_arrangement_edit(project_dir: Path) -> ArrangementEditTransaction:
    project = project_dir.expanduser().resolve()
    history = load_current_arrangement_edit_history(project)
    if not history.can_redo:
        raise ValueError("No accepted arrangement edit is available to redo")
    transaction = history.transactions[history.cursor]
    if not all(_snapshot_matches_disk(project, item) for item in transaction.before):
        raise ValueError("Cannot redo because a managed review layer changed outside arrangement edit history")
    _apply_snapshots(project, transaction.after)
    updated = history.model_copy(update={"cursor": history.cursor + 1})
    try:
        _write_history(project, updated)
    except Exception:
        _apply_snapshots(project, transaction.before)
        raise
    return transaction
