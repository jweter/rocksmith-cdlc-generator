from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from .arrangement_edit_history import record_arrangement_review_edit
from .hashing import sha256_file
from .score_fanout import ScoreFanoutEntry, ScoreFanoutManifest
from .score_mapping_review import load_score_for_mapping_review
from .score_role_composition import (
    ScoreRoleCompositionPlan,
    validate_score_role_composition,
)
from .score_role_composition_fanout_review import (
    ScoreRoleCompositionFanoutReviewLayer,
    load_current_score_role_composition_fanout,
)
from .score_role_composition_fanout_review import (
    _load_current_locked as _load_current_composition_fanout_locked,
)
from .score_role_composition_review import SCORE_ROLE_COMPOSITION_PATH
from .score_source import ArrangementRole, ProjectScoreSource
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


def _resolve_composed_review_entry(
    project: Path,
    arrangement: ArrangementRoleName,
    *,
    score: ProjectScoreSource,
    entry: ScoreFanoutEntry,
    load_composition_fanout: Callable[
        [Path], ScoreRoleCompositionFanoutReviewLayer | None
    ],
) -> ScoreFanoutEntry:
    """Return ``entry``, or an entry pointing at the composed multi-track note stream, for
    position/event-timing/technique/chord review and the Arrangement Preview to actually
    consume (issue #232).

    These layers (this module and ``reviewed_event_timing.py``/``reviewed_techniques.py``/
    ``reviewed_chords.py``, all of which route through ``_fanout_entry``/``_source_event``,
    plus ``score_preview.py``'s read-only Arrangement Preview snapshot) key every
    decision/preview note by an index into exactly one score fan-out output's note list
    (``entry.output_json``). Bass's composed multi-track fan-out (``score_fanout.py``'s
    ``_materialize_composed_bass_source``) is already written into the score fan-out
    manifest itself, so ``entry.output_json`` already names the composed note stream for
    Bass -- this returns ``entry`` unchanged for Bass, verifying that invariant still holds
    rather than assuming it. Lead/Rhythm's composed multi-track note stream is instead
    materialized only inside ``shared_guitar.py``'s chart-build path
    (``_materialize_composed_guitar_source``), entirely separate from the score fan-out
    manifest this module and ``score_preview.py`` read -- so for Lead/Rhythm with a
    currently selected multi-track composition, this re-materializes that exact same
    composed source directly from the current persisted ``RoleCompositionFanoutRecord``
    and returns a copy of ``entry`` whose ``output_json`` names it instead, so every
    existing per-event-index consumer downstream of ``_fanout_entry``/``_source_event``
    (and score_preview.py's own note-assembly loop) sees the full composed stream without
    any further change to their own indexing logic -- the same shape
    ``_materialize_composed_guitar_source`` already produces for
    ``_build_project_shared_guitar_chart_locked``.

    A missing, stale, or unreadable composition plan, or a selection of at most one
    track, is "nothing to override" and returns ``entry`` unchanged -- mirroring
    ``shared_guitar._current_composed_record_for_role``/``score_fanout.
    _current_composed_bass_record``: this is a best-effort read of the *plan*, not the
    authoritative plan validator. A selection of more than one track with no current
    composed fan-out record yet still fails closed, with the same actionable "not yet
    composed" guidance those two functions already give -- that genuinely ambiguous/
    unbuilt case is not weakened by this change, only the ordinary already-composed case
    is no longer rejected.
    """

    plan_path = project / SCORE_ROLE_COMPOSITION_PATH
    if not plan_path.is_file():
        return entry
    try:
        plan = ScoreRoleCompositionPlan.model_validate_json(plan_path.read_text(encoding="utf-8"))
        plan = validate_score_role_composition(score, plan)
    except (OSError, ValueError, ValidationError):
        return entry
    role = ArrangementRole(arrangement)
    selection = plan.selection_for(role)
    if selection is None or len(selection.source_track_indices) <= 1:
        return entry

    expected_composed_relative = (
        Path("sources") / "imported" / "composition" / f"{arrangement}-composed-{score.source_sha256[:12]}.json"
    ).as_posix()

    if arrangement == "bass":
        if entry.output_json == expected_composed_relative:
            return entry
        raise ValueError(
            f"bass currently has {len(selection.source_track_indices)} score tracks selected via score "
            "role composition, but the current score fan-out output does not name the composed multi-"
            "track source; run score fan-out again to rebuild it before reviewing or previewing this "
            "arrangement."
        )

    layer = load_composition_fanout(project)
    record = None if layer is None else layer.record_for(role)
    if record is None:
        raise ValueError(
            f"{arrangement} currently has {len(selection.source_track_indices)} score tracks selected via "
            "score role composition, but no current composed fan-out record exists for it yet; position/"
            "event-timing/technique/chord review and the Arrangement Preview would otherwise only see the "
            "single confirmed-primary-track fan-out output. Compose this role's multi-track selection "
            "(resolve any overlap findings, then run score role composition fan-out) before reviewing or "
            "previewing this arrangement."
        )

    # Deferred import: shared_guitar.py imports this module at module scope (for
    # apply_reviewed_positions/current_reviewed_positions_sha256), so importing it back
    # here at module scope would be a circular import.
    from .shared_guitar import _materialize_composed_guitar_source

    composed_path = _materialize_composed_guitar_source(project, role=role, record=record)
    composed_relative = composed_path.relative_to(project).as_posix()
    if composed_relative != expected_composed_relative:
        raise ValueError(f"{arrangement} composed review source path is unexpected: {composed_relative}")
    return entry.model_copy(update={"output_json": composed_relative})


def resolve_composed_review_entry(
    project: Path,
    arrangement: ArrangementRoleName,
    *,
    score: ProjectScoreSource,
    entry: ScoreFanoutEntry,
) -> ScoreFanoutEntry:
    """Resolve the review source when the caller does not hold the score lock."""

    return _resolve_composed_review_entry(
        project,
        arrangement,
        score=score,
        entry=entry,
        load_composition_fanout=load_current_score_role_composition_fanout,
    )


def _resolve_composed_review_entry_locked(
    project: Path,
    arrangement: ArrangementRoleName,
    *,
    score: ProjectScoreSource,
    entry: ScoreFanoutEntry,
) -> ScoreFanoutEntry:
    """Resolve the review source while the caller already holds the score lock."""

    return _resolve_composed_review_entry(
        project,
        arrangement,
        score=score,
        entry=entry,
        load_composition_fanout=_load_current_composition_fanout_locked,
    )


def _fanout_entry(project: Path, arrangement: ArrangementRoleName):
    _path, manifest = _current_fanout(project)
    entry = next((item for item in manifest.arrangements if item.role.value == arrangement), None)
    if entry is None:
        raise ValueError(f"Current score fan-out has no {arrangement} arrangement")
    score = load_score_for_mapping_review(project)
    mapping = score.mapping_for(entry.role)
    if mapping is None or not mapping.human_confirmed or mapping.source_track_index != entry.source_track_index:
        raise ValueError(f"{arrangement} score mapping is no longer human-confirmed/current")
    return resolve_composed_review_entry(project, arrangement, score=score, entry=entry)


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
        score_sha256=layer.score_sha256,
        score_format=layer.score_format,
        fanout_manifest_path=layer.fanout_manifest_path,
        fanout_manifest_sha256=layer.fanout_manifest_sha256,
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
