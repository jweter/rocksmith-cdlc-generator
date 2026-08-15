from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .arrangement_edit_history import record_arrangement_review_edit
from .hashing import sha256_file
from .score_fanout import ScoreFanoutManifest
from .score_mapping_review import load_score_for_mapping_review
from .source_import import ImportedSource

ArrangementRoleName = Literal["bass", "lead", "rhythm"]


class ReviewedPositionDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    arrangement: ArrangementRoleName
    source_track_index: int = Field(ge=0)
    event_index: int = Field(ge=0)
    source_start_seconds: float = Field(ge=0)
    midi: int = Field(ge=0, le=127)
    string_index: int = Field(ge=0)
    fret: int = Field(ge=0)
    accepted_at: datetime


class ReviewedPositionLayer(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    score_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    score_format: str
    fanout_manifest_path: str
    fanout_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    decisions: list[ReviewedPositionDecision] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_event_keys(self) -> "ReviewedPositionLayer":
        keys = [
            (item.arrangement, item.source_track_index, item.event_index)
            for item in self.decisions
        ]
        if len(keys) != len(set(keys)):
            raise ValueError("reviewed position layer contains duplicate event decisions")
        return self

    def decision_for(
        self,
        arrangement: ArrangementRoleName,
        source_track_index: int,
        event_index: int,
    ) -> ReviewedPositionDecision | None:
        return next(
            (
                item
                for item in self.decisions
                if item.arrangement == arrangement
                and item.source_track_index == source_track_index
                and item.event_index == event_index
            ),
            None,
        )


POSITION_REVIEW_PATH = Path("review") / "reviewed_positions.json"


def _current_fanout(project: Path) -> tuple[Path, ScoreFanoutManifest]:
    score = load_score_for_mapping_review(project)
    path = project / "sources" / "imported" / f"score-fanout-{score.source_sha256[:12]}.json"
    if not path.is_file():
        raise FileNotFoundError("Current score fan-out manifest is not available")
    manifest = ScoreFanoutManifest.model_validate_json(path.read_text(encoding="utf-8"))
    if manifest.score_source_sha256 != score.source_sha256 or manifest.score_source_format != score.source_format:
        raise ValueError("Current score fan-out does not match the registered score")
    return path, manifest


def load_current_reviewed_positions(project_dir: Path) -> ReviewedPositionLayer | None:
    project = project_dir.expanduser().resolve()
    review_path = project / POSITION_REVIEW_PATH
    if not review_path.is_file():
        return None
    score = load_score_for_mapping_review(project)
    fanout_path, _manifest = _current_fanout(project)
    layer = ReviewedPositionLayer.model_validate_json(review_path.read_text(encoding="utf-8"))
    if layer.score_sha256 != score.source_sha256 or layer.score_format != score.source_format:
        raise ValueError("Reviewed position layer is stale for the registered score")
    expected_relative = fanout_path.relative_to(project).as_posix()
    if layer.fanout_manifest_path != expected_relative:
        raise ValueError("Reviewed position layer points at a stale score fan-out")
    if layer.fanout_manifest_sha256 != sha256_file(fanout_path):
        raise ValueError("Reviewed position layer is stale for the current score fan-out")
    return layer


def current_reviewed_positions_sha256(project_dir: Path) -> str | None:
    project = project_dir.expanduser().resolve()
    layer = load_current_reviewed_positions(project)
    if layer is None:
        return None
    return sha256_file(project / POSITION_REVIEW_PATH)


def _fanout_entry(project: Path, arrangement: ArrangementRoleName):
    _path, manifest = _current_fanout(project)
    entry = next((item for item in manifest.arrangements if item.role.value == arrangement), None)
    if entry is None:
        raise ValueError(f"Current score fan-out has no {arrangement} arrangement")
    score = load_score_for_mapping_review(project)
    mapping = score.mapping_for(entry.role)
    if mapping is None or not mapping.human_confirmed or mapping.source_track_index != entry.source_track_index:
        raise ValueError(f"{arrangement} score mapping is no longer human-confirmed/current")
    return entry


def _source_event(project: Path, arrangement: ArrangementRoleName, event_index: int):
    entry = _fanout_entry(project, arrangement)
    source_path = (project / entry.output_json).resolve()
    if not source_path.is_relative_to(project) or not source_path.is_file():
        raise ValueError(f"{arrangement} fan-out source is not a safe project-local file")
    imported = ImportedSource.read_json(source_path)
    if len(imported.tracks) != 1:
        raise ValueError(f"{arrangement} fan-out must contain exactly one source track")
    track = imported.tracks[0]
    if track.source_track_index != entry.source_track_index or track.instrument != arrangement:
        raise ValueError(f"{arrangement} fan-out source no longer matches current authority")
    if event_index < 0 or event_index >= len(track.notes):
        raise IndexError(f"{arrangement} event index is out of range")
    return entry, track, track.notes[event_index]


def set_reviewed_position(
    project_dir: Path,
    *,
    arrangement: ArrangementRoleName,
    event_index: int,
    string_index: int,
    fret: int,
) -> ReviewedPositionLayer:
    """Record one explicit human-approved physical position without mutating source artifacts."""

    project = project_dir.expanduser().resolve()
    fanout_path, _manifest = _current_fanout(project)
    score = load_score_for_mapping_review(project)
    entry, track, note = _source_event(project, arrangement, event_index)

    if track.tuning_midi is None:
        raise ValueError(f"{arrangement} position review requires explicit source tuning")
    if string_index < 0 or string_index >= len(track.tuning_midi):
        raise ValueError(f"string index {string_index} is outside the {len(track.tuning_midi)}-string tuning")
    if fret < 0:
        raise ValueError("fret must be non-negative")
    if int(track.tuning_midi[string_index]) + fret != note.midi:
        raise ValueError("reviewed string/fret position does not produce the source MIDI pitch")

    current = load_current_reviewed_positions(project)
    decisions = [] if current is None else list(current.decisions)
    key = (arrangement, entry.source_track_index, event_index)
    decisions = [
        item
        for item in decisions
        if (item.arrangement, item.source_track_index, item.event_index) != key
    ]
    decisions.append(
        ReviewedPositionDecision(
            arrangement=arrangement,
            source_track_index=entry.source_track_index,
            event_index=event_index,
            source_start_seconds=note.start_seconds,
            midi=note.midi,
            string_index=string_index,
            fret=fret,
            accepted_at=datetime.now(timezone.utc),
        )
    )
    decisions.sort(key=lambda item: (item.arrangement, item.source_track_index, item.event_index))
    layer = ReviewedPositionLayer(
        score_sha256=score.source_sha256,
        score_format=score.source_format,
        fanout_manifest_path=fanout_path.relative_to(project).as_posix(),
        fanout_manifest_sha256=sha256_file(fanout_path),
        decisions=decisions,
    )
    record_arrangement_review_edit(
        project,
        kind="position",
        writes={POSITION_REVIEW_PATH: layer.model_dump_json(indent=2) + "\n"},
    )
    return layer


def apply_reviewed_positions(
    project_dir: Path,
    source: ImportedSource,
    *,
    arrangement: ArrangementRoleName,
    source_track_index: int,
) -> tuple[ImportedSource, set[int]]:
    """Return a copied source with current reviewed string/fret decisions overlaid."""

    layer = load_current_reviewed_positions(project_dir)
    if layer is None:
        return source.model_copy(deep=True), set()
    copied = source.model_copy(deep=True)
    tracks = [
        track
        for track in copied.tracks
        if track.instrument == arrangement and track.source_track_index == source_track_index
    ]
    if len(tracks) != 1:
        raise ValueError(f"Expected exactly one {arrangement} track for reviewed position overlay")
    track = tracks[0]
    applied: set[int] = set()
    for decision in layer.decisions:
        if decision.arrangement != arrangement or decision.source_track_index != source_track_index:
            continue
        if decision.event_index >= len(track.notes):
            raise ValueError("Reviewed position event index is stale for current fan-out")
        note = track.notes[decision.event_index]
        if note.midi != decision.midi or abs(note.start_seconds - decision.source_start_seconds) > 1e-6:
            raise ValueError("Reviewed position event identity is stale for current fan-out")
        note.string_index = decision.string_index
        note.fret = decision.fret
        applied.add(decision.event_index)
    return copied, applied
