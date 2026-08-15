from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .arrangement_edit_history import record_arrangement_review_edit
from .hashing import sha256_file
from .reviewed_positions import _current_fanout, _source_event
from .score_mapping_review import load_score_for_mapping_review

GuitarRole = Literal["lead", "rhythm"]
CHORD_REVIEW_PATH = Path("review") / "reviewed_chords.json"
DEFAULT_MAX_SOURCE_SPAN_SECONDS = 0.125


class ReviewedChordMember(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_index: int = Field(ge=0)
    source_start_seconds: float = Field(ge=0)
    midi: int = Field(ge=0, le=127)


class ReviewedChordDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    arrangement: GuitarRole
    source_track_index: int = Field(ge=0)
    members: list[ReviewedChordMember] = Field(min_length=2)
    accepted_at: datetime

    @model_validator(mode="after")
    def validate_members(self) -> "ReviewedChordDecision":
        indices = [item.event_index for item in self.members]
        if indices != sorted(indices):
            raise ValueError("reviewed chord members must be sorted by event index")
        if len(indices) != len(set(indices)):
            raise ValueError("reviewed chord contains duplicate event indices")
        return self

    @property
    def event_indices(self) -> list[int]:
        return [item.event_index for item in self.members]


class ReviewedChordLayer(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    score_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    score_format: str
    fanout_manifest_path: str
    fanout_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    decisions: list[ReviewedChordDecision] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_membership(self) -> "ReviewedChordLayer":
        seen: set[tuple[str, int, int]] = set()
        for decision in self.decisions:
            for event_index in decision.event_indices:
                key = (decision.arrangement, decision.source_track_index, event_index)
                if key in seen:
                    raise ValueError("reviewed chord layer assigns one event to multiple chords")
                seen.add(key)
        return self


def load_current_reviewed_chords(project_dir: Path) -> ReviewedChordLayer | None:
    project = project_dir.expanduser().resolve()
    path = project / CHORD_REVIEW_PATH
    if not path.is_file():
        return None
    score = load_score_for_mapping_review(project)
    fanout_path, _manifest = _current_fanout(project)
    layer = ReviewedChordLayer.model_validate_json(path.read_text(encoding="utf-8"))
    if layer.score_sha256 != score.source_sha256 or layer.score_format != score.source_format:
        raise ValueError("Reviewed chord layer is stale for the registered score")
    expected = fanout_path.relative_to(project).as_posix()
    if layer.fanout_manifest_path != expected:
        raise ValueError("Reviewed chord layer points at a stale score fan-out")
    if layer.fanout_manifest_sha256 != sha256_file(fanout_path):
        raise ValueError("Reviewed chord layer is stale for the current score fan-out")

    for decision in layer.decisions:
        for member in decision.members:
            entry, _track, note = _source_event(
                project, decision.arrangement, member.event_index
            )
            if entry.source_track_index != decision.source_track_index:
                raise ValueError("Reviewed chord layer is stale for the current source track")
            if abs(note.start_seconds - member.source_start_seconds) > 1e-9 or note.midi != member.midi:
                raise ValueError("Reviewed chord layer is stale for a source event identity")
    return layer


def current_reviewed_chords_sha256(project_dir: Path) -> str | None:
    project = project_dir.expanduser().resolve()
    layer = load_current_reviewed_chords(project)
    if layer is None:
        return None
    return sha256_file(project / CHORD_REVIEW_PATH)


def reviewed_chord_groups(
    project_dir: Path,
    *,
    arrangement: GuitarRole,
    source_track_index: int,
) -> list[list[int]]:
    layer = load_current_reviewed_chords(project_dir)
    if layer is None:
        return []
    return [
        decision.event_indices
        for decision in layer.decisions
        if decision.arrangement == arrangement
        and decision.source_track_index == source_track_index
    ]


def set_reviewed_chord_group(
    project_dir: Path,
    *,
    arrangement: GuitarRole,
    event_indices: list[int],
    max_source_span_seconds: float = DEFAULT_MAX_SOURCE_SPAN_SECONDS,
) -> ReviewedChordLayer:
    """Accept one explicit source-event chord identity without changing note/timing authority."""

    if max_source_span_seconds <= 0:
        raise ValueError("maximum chord source span must be positive")
    normalized = sorted(event_indices)
    if len(normalized) < 2:
        raise ValueError("reviewed chord requires at least two source events")
    if len(normalized) != len(set(normalized)):
        raise ValueError("reviewed chord contains duplicate event indices")

    project = project_dir.expanduser().resolve()
    fanout_path, _manifest = _current_fanout(project)
    score = load_score_for_mapping_review(project)

    members: list[ReviewedChordMember] = []
    source_track_index: int | None = None
    starts: list[float] = []
    for event_index in normalized:
        entry, _track, note = _source_event(project, arrangement, event_index)
        if source_track_index is None:
            source_track_index = entry.source_track_index
        elif source_track_index != entry.source_track_index:
            raise ValueError("reviewed chord events do not share one source track")
        starts.append(note.start_seconds)
        members.append(
            ReviewedChordMember(
                event_index=event_index,
                source_start_seconds=note.start_seconds,
                midi=note.midi,
            )
        )
    if max(starts) - min(starts) > max_source_span_seconds:
        raise ValueError(
            f"reviewed chord source events span more than {max_source_span_seconds:.3f}s"
        )

    try:
        current = load_current_reviewed_chords(project)
    except ValueError as exc:
        if "stale" not in str(exc).lower():
            raise
        current = None
    decisions = [] if current is None else list(current.decisions)
    selected = set(normalized)
    decisions = [
        decision
        for decision in decisions
        if not (
            decision.arrangement == arrangement
            and decision.source_track_index == source_track_index
            and selected.intersection(decision.event_indices)
        )
    ]
    decisions.append(
        ReviewedChordDecision(
            arrangement=arrangement,
            source_track_index=source_track_index,
            members=members,
            accepted_at=datetime.now(timezone.utc),
        )
    )
    decisions.sort(
        key=lambda item: (
            item.arrangement,
            item.source_track_index,
            item.event_indices[0],
        )
    )
    layer = ReviewedChordLayer(
        score_sha256=score.source_sha256,
        score_format=score.source_format,
        fanout_manifest_path=fanout_path.relative_to(project).as_posix(),
        fanout_manifest_sha256=sha256_file(fanout_path),
        decisions=decisions,
    )
    record_arrangement_review_edit(
        project,
        kind="chord_identity",
        writes={CHORD_REVIEW_PATH: layer.model_dump_json(indent=2) + "\n"},
        score_sha256=layer.score_sha256,
        score_format=layer.score_format,
        fanout_manifest_path=layer.fanout_manifest_path,
        fanout_manifest_sha256=layer.fanout_manifest_sha256,
    )
    return layer
