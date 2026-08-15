from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .arrangement_edit_history import record_arrangement_review_edit
from .hashing import sha256_file
from .reviewed_positions import _current_fanout, _source_event
from .score_mapping_review import load_score_for_mapping_review
from .source_import import ImportedSource

ArrangementRoleName = Literal["bass", "lead", "rhythm"]
TECHNIQUE_REVIEW_PATH = Path("review") / "reviewed_techniques.json"
SUPPORTED_TECHNIQUES: tuple[str, ...] = (
    "accent",
    "bend",
    "ghost_note",
    "grace",
    "hammer_on_pull_off",
    "harmonic",
    "heavy_accent",
    "let_ring",
    "palm_mute",
    "slide",
    "staccato",
    "tie",
    "tremolo_picking",
    "trill",
    "vibrato",
)
_SUPPORTED_TECHNIQUE_SET = frozenset(SUPPORTED_TECHNIQUES)


class ReviewedTechniqueDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    arrangement: ArrangementRoleName
    source_track_index: int = Field(ge=0)
    event_index: int = Field(ge=0)
    source_start_seconds: float = Field(ge=0)
    source_duration_seconds: float = Field(gt=0)
    midi: int = Field(ge=0, le=127)
    source_techniques: list[str] = Field(default_factory=list)
    reviewed_techniques: list[str] = Field(default_factory=list)
    accepted_at: datetime


class ReviewedTechniqueLayer(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    score_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    score_format: str
    fanout_manifest_path: str
    fanout_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    decisions: list[ReviewedTechniqueDecision] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_event_keys(self) -> "ReviewedTechniqueLayer":
        keys = [
            (item.arrangement, item.source_track_index, item.event_index)
            for item in self.decisions
        ]
        if len(keys) != len(set(keys)):
            raise ValueError("reviewed technique layer contains duplicate event decisions")
        return self

    def decision_for(
        self,
        arrangement: ArrangementRoleName,
        source_track_index: int,
        event_index: int,
    ) -> ReviewedTechniqueDecision | None:
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


def _normalize_techniques(techniques: list[str] | tuple[str, ...]) -> list[str]:
    normalized = sorted({str(item).strip().lower() for item in techniques if str(item).strip()})
    unsupported = [item for item in normalized if item not in _SUPPORTED_TECHNIQUE_SET]
    if unsupported:
        supported = ", ".join(SUPPORTED_TECHNIQUES)
        raise ValueError(
            f"Unsupported technique(s): {', '.join(unsupported)}. Supported values: {supported}"
        )
    return normalized


def validate_decision_identity(project_dir: Path, decision: ReviewedTechniqueDecision) -> None:
    project = project_dir.expanduser().resolve()
    entry, _track, note = _source_event(project, decision.arrangement, decision.event_index)
    if entry.source_track_index != decision.source_track_index:
        raise ValueError("Reviewed technique source track is stale")
    if note.midi != decision.midi:
        raise ValueError("Reviewed technique MIDI identity is stale")
    if abs(note.start_seconds - decision.source_start_seconds) > 1e-6:
        raise ValueError("Reviewed technique source onset identity is stale")
    if abs(note.duration_seconds - decision.source_duration_seconds) > 1e-6:
        raise ValueError("Reviewed technique source duration identity is stale")
    if list(note.techniques) != decision.source_techniques:
        raise ValueError("Reviewed technique source technique identity is stale")


def load_current_reviewed_techniques(project_dir: Path) -> ReviewedTechniqueLayer | None:
    project = project_dir.expanduser().resolve()
    destination = project / TECHNIQUE_REVIEW_PATH
    if not destination.is_file():
        return None

    score = load_score_for_mapping_review(project)
    fanout_path, _manifest = _current_fanout(project)
    layer = ReviewedTechniqueLayer.model_validate_json(destination.read_text(encoding="utf-8"))
    if layer.score_sha256 != score.source_sha256 or layer.score_format != score.source_format:
        raise ValueError("Reviewed technique layer is stale for the registered score")
    if layer.fanout_manifest_path != fanout_path.relative_to(project).as_posix():
        raise ValueError("Reviewed technique layer points at a stale score fan-out")
    if layer.fanout_manifest_sha256 != sha256_file(fanout_path):
        raise ValueError("Reviewed technique layer is stale for the current score fan-out")
    for decision in layer.decisions:
        validate_decision_identity(project, decision)
    return layer


def current_reviewed_techniques_sha256(project_dir: Path) -> str | None:
    project = project_dir.expanduser().resolve()
    layer = load_current_reviewed_techniques(project)
    if layer is None:
        return None
    return sha256_file(project / TECHNIQUE_REVIEW_PATH)


def set_reviewed_techniques(
    project_dir: Path,
    *,
    arrangement: ArrangementRoleName,
    event_index: int,
    techniques: list[str] | tuple[str, ...],
) -> ReviewedTechniqueLayer:
    """Accept one event's technique set without mutating imported score/fan-out data."""

    project = project_dir.expanduser().resolve()
    reviewed_techniques = _normalize_techniques(techniques)
    score = load_score_for_mapping_review(project)
    fanout_path, _manifest = _current_fanout(project)
    entry, _track, note = _source_event(project, arrangement, event_index)

    replacing_stale = False
    try:
        current = load_current_reviewed_techniques(project)
    except ValueError as exc:
        if "stale" not in str(exc).lower():
            raise
        current = None
        replacing_stale = True

    decisions = [] if current is None else list(current.decisions)
    key = (arrangement, entry.source_track_index, event_index)
    decisions = [
        item
        for item in decisions
        if (item.arrangement, item.source_track_index, item.event_index) != key
    ]
    decisions.append(
        ReviewedTechniqueDecision(
            arrangement=arrangement,
            source_track_index=entry.source_track_index,
            event_index=event_index,
            source_start_seconds=note.start_seconds,
            source_duration_seconds=note.duration_seconds,
            midi=note.midi,
            source_techniques=list(note.techniques),
            reviewed_techniques=reviewed_techniques,
            accepted_at=datetime.now(timezone.utc),
        )
    )
    decisions.sort(key=lambda item: (item.arrangement, item.source_track_index, item.event_index))

    layer = ReviewedTechniqueLayer(
        score_sha256=score.source_sha256,
        score_format=score.source_format,
        fanout_manifest_path=fanout_path.relative_to(project).as_posix(),
        fanout_manifest_sha256=sha256_file(fanout_path),
        decisions=decisions,
    )
    record_arrangement_review_edit(
        project,
        kind="techniques",
        writes={TECHNIQUE_REVIEW_PATH: layer.model_dump_json(indent=2) + "\n"},
        score_sha256=layer.score_sha256,
        score_format=layer.score_format,
        fanout_manifest_path=layer.fanout_manifest_path,
        fanout_manifest_sha256=layer.fanout_manifest_sha256,
        logical_before_overrides={TECHNIQUE_REVIEW_PATH: None} if replacing_stale else None,
    )
    return layer


def technique_overrides_for_arrangement(
    project_dir: Path,
    *,
    arrangement: ArrangementRoleName,
    source_track_index: int,
) -> dict[int, list[str]]:
    layer = load_current_reviewed_techniques(project_dir)
    if layer is None:
        return {}
    return {
        item.event_index: list(item.reviewed_techniques)
        for item in layer.decisions
        if item.arrangement == arrangement and item.source_track_index == source_track_index
    }


def apply_reviewed_techniques_to_source(
    project_dir: Path,
    source: ImportedSource,
    *,
    arrangement: ArrangementRoleName,
    source_track_index: int,
    allow_stale_as_unreviewed: bool = False,
) -> tuple[ImportedSource, set[int]]:
    """Return a deep copy with current human-reviewed technique sets overlaid.

    Normal authoring remains fail-closed. Read-only preview may opt into treating a stale
    derivative review layer as no current overlay so the user can select an event and
    explicitly replace that obsolete authority in the GUI.
    """

    try:
        overrides = technique_overrides_for_arrangement(
            project_dir,
            arrangement=arrangement,
            source_track_index=source_track_index,
        )
    except ValueError as exc:
        if not allow_stale_as_unreviewed or "stale" not in str(exc).lower():
            raise
        overrides = {}

    copied = source.model_copy(deep=True)
    if not overrides:
        return copied, set()

    track = next(
        (
            item
            for item in copied.tracks
            if item.instrument == arrangement and item.source_track_index == source_track_index
        ),
        None,
    )
    if track is None:
        raise ValueError(f"Expected current {arrangement} track for reviewed technique overlay")

    applied: set[int] = set()
    for event_index, reviewed_techniques in overrides.items():
        if event_index >= len(track.notes):
            raise ValueError("Reviewed technique index is stale for current fan-out")
        track.notes[event_index].techniques = list(reviewed_techniques)
        applied.add(event_index)
    return copied, applied
