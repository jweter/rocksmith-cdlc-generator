from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from .hashing import sha256_file
from .reviewed_positions import resolve_composed_review_entry
from .score_fanout import ScoreFanoutManifest
from .score_mapping_review import load_score_for_mapping_review
from .score_source import ProjectScoreSource
from .source_import import ImportedSource

MarkState = Literal["questionable", "wrong"]
MarkScope = Literal["note", "chord"]
REVIEW_MARKS_PATH = Path("review/human_note_marks.json")


class HumanNoteReviewMark(BaseModel):
    arrangement: str
    event_index: int = Field(ge=0)
    source_start_seconds: float = Field(ge=0)
    midi: int = Field(ge=0, le=127)
    string_index: int | None = Field(default=None, ge=0)
    fret: int | None = Field(default=None, ge=0)
    state: MarkState
    scope: MarkScope = "note"
    marked_at: datetime


class HumanNoteReviewLayer(BaseModel):
    schema_version: int = 1
    source_sha256: str
    # Marks were previously keyed on ``source_sha256`` alone. A human-confirmed role
    # mapping or composed multi-track selection change can replace which notes an
    # arrangement's event indices actually point at without changing the registered
    # score's own SHA256 (``score_mapping_review.confirm_score_mapping`` intentionally
    # deletes only the fan-out manifest, leaving the original score bytes untouched), so
    # a stale mark could otherwise keep loading as "current" and silently attach to an
    # unrelated event. These two fields bind the layer to the current score fan-out
    # manifest's own path and content hash -- the same identity
    # ``reviewed_positions.py``/``reviewed_techniques.py``/``reviewed_chords.py``/
    # ``reviewed_event_timing.py`` already require for exactly this class of staleness.
    # They are ``None`` only for projects with no score/fan-out apparatus at all (e.g. a
    # bare/legacy project), which keeps this module's pre-existing SHA-only behavior for
    # that case.
    fanout_manifest_path: str | None = None
    fanout_manifest_sha256: str | None = None
    marks: list[HumanNoteReviewMark] = Field(default_factory=list)


def _current_score(project: Path) -> ProjectScoreSource | None:
    """Return the registered score for ``project``, or ``None`` if none is registered.

    A score that *is* registered but whose stored contract/bytes fail integrity checks
    is a genuine problem elsewhere in the project, not "no score" -- so only the
    "nothing registered yet" cases are swallowed here.
    """

    try:
        return load_score_for_mapping_review(project)
    except (OSError, ValueError):
        return None


def _current_fanout_identity(project: Path, score: ProjectScoreSource) -> tuple[str, str] | None:
    """Return (fanout_manifest_relative_path, fanout_manifest_sha256) for the fan-out
    manifest currently registered for ``score``, or ``None`` if it is missing or stale.
    """

    manifest_path = project / "sources" / "imported" / f"score-fanout-{score.source_sha256[:12]}.json"
    if not manifest_path.is_file():
        return None
    try:
        manifest = ScoreFanoutManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if manifest.score_source_sha256 != score.source_sha256 or manifest.score_source_format != score.source_format:
        return None
    return manifest_path.relative_to(project).as_posix(), sha256_file(manifest_path)


def _resolve_current_event_signature(
    project: Path, score: ProjectScoreSource, arrangement: str, event_index: int
) -> tuple[int, float] | None:
    """Return (midi, start_seconds) for the live current event at this arrangement/index.

    This resolves through the current score fan-out, including any composed
    multi-track selection override (``resolve_composed_review_entry``), so it reflects
    exactly what the Arrangement Preview and packaging inputs currently show for that
    index -- not just the base fan-out manifest, which a Lead/Rhythm composed-track
    selection change does not itself modify. Returns ``None`` when the event cannot be
    resolved for any reason (missing manifest, unknown role, stale composition, index
    out of range, ...); callers must treat that as "cannot verify", not "matches".
    """

    manifest_path = project / "sources" / "imported" / f"score-fanout-{score.source_sha256[:12]}.json"
    if not manifest_path.is_file():
        return None
    try:
        manifest = ScoreFanoutManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
        if manifest.score_source_sha256 != score.source_sha256 or manifest.score_source_format != score.source_format:
            return None
        entry = next((item for item in manifest.arrangements if item.role.value == arrangement), None)
        if entry is None:
            return None
        entry = resolve_composed_review_entry(project, arrangement, score=score, entry=entry)
        output = (project / entry.output_json).resolve()
        if not output.is_relative_to(project) or not output.is_file():
            return None
        imported = ImportedSource.read_json(output)
    except (OSError, ValueError):
        return None
    if len(imported.tracks) != 1:
        return None
    track = imported.tracks[0]
    if track.instrument != arrangement or track.source_track_index != entry.source_track_index:
        return None
    if event_index < 0 or event_index >= len(track.notes):
        return None
    note = track.notes[event_index]
    return note.midi, note.start_seconds


def load_human_review_layer(project_dir: Path) -> HumanNoteReviewLayer | None:
    path = project_dir.resolve() / REVIEW_MARKS_PATH
    if not path.is_file():
        return None
    return HumanNoteReviewLayer.model_validate_json(path.read_text(encoding="utf-8"))


def load_current_human_review_layer(project_dir: Path, source_sha256: str) -> HumanNoteReviewLayer | None:
    """Return the persisted mark layer only if it is bound to the current arrangement identity.

    This is the cheap identity check (score SHA plus the small fan-out manifest's own
    path/hash) that is safe to call on every GUI refresh; it catches a role-mapping
    change and a Bass composed-track-selection change (both of which change the fan-out
    manifest itself). It intentionally does not re-read every arrangement's full note
    stream on each call -- see ``current_marks_for_arrangement`` for the additional,
    more expensive per-event signature check used before marks are allowed to gate
    packaging.
    """

    project = project_dir.resolve()
    layer = load_human_review_layer(project)
    if layer is None or layer.source_sha256 != source_sha256:
        return None
    score = _current_score(project)
    if score is None:
        # No score/fan-out apparatus registered for this project at all: keep the
        # pre-existing SHA-only identity behavior.
        return layer
    if score.source_sha256 != source_sha256:
        return None
    identity = _current_fanout_identity(project, score)
    if identity is None:
        return None
    fanout_path, fanout_sha256 = identity
    if layer.fanout_manifest_path != fanout_path or layer.fanout_manifest_sha256 != fanout_sha256:
        return None
    return layer


def current_marks_for_arrangement(
    project_dir: Path, source_sha256: str, arrangement: str
) -> list[HumanNoteReviewMark]:
    """Marks for ``arrangement`` that are safe to project into validation/packaging.

    Beyond ``load_current_human_review_layer``'s cheap file-identity check, this
    additionally verifies each mark's own stored (MIDI, onset) against the arrangement's
    live current event at that index, resolved through any composed multi-track
    selection override. That closes the one gap the cheap check cannot: a Lead/Rhythm
    composed-track-selection change is applied downstream of the fan-out manifest and
    does not change the manifest's own hash, so only a per-event signature check can
    detect it. A mark that no longer matches the current event at its index is dropped
    rather than misapplied to an unrelated event.
    """

    project = project_dir.resolve()
    layer = load_current_human_review_layer(project, source_sha256)
    if layer is None:
        return []
    relevant = [mark for mark in layer.marks if mark.arrangement == arrangement]
    if not relevant:
        return []
    score = _current_score(project)
    if score is None:
        # No score/fan-out apparatus to verify against: honor the file-identity-bound
        # marks as-is (legacy/test project behavior).
        return relevant
    verified: list[HumanNoteReviewMark] = []
    for mark in relevant:
        signature = _resolve_current_event_signature(project, score, arrangement, mark.event_index)
        if signature is None:
            continue
        midi, start_seconds = signature
        if midi == mark.midi and abs(start_seconds - mark.source_start_seconds) <= 1e-6:
            verified.append(mark)
    return verified


def mark_event(
    project_dir: Path,
    *,
    source_sha256: str,
    arrangement: str,
    event_index: int,
    source_start_seconds: float,
    midi: int,
    string_index: int | None,
    fret: int | None,
    state: MarkState,
    scope: MarkScope = "note",
) -> HumanNoteReviewLayer:
    project = project_dir.resolve()
    fanout_manifest_path: str | None = None
    fanout_manifest_sha256: str | None = None
    score = _current_score(project)
    if score is not None:
        if score.source_sha256 != source_sha256:
            raise ValueError("Mark source SHA does not match the currently registered score")
        identity = _current_fanout_identity(project, score)
        if identity is None:
            raise ValueError("Cannot record a human mark: no current score fan-out is available")
        fanout_manifest_path, fanout_manifest_sha256 = identity

    current = load_current_human_review_layer(project, source_sha256)
    marks = [] if current is None else list(current.marks)
    marks = [m for m in marks if not (m.arrangement == arrangement and m.event_index == event_index)]
    marks.append(
        HumanNoteReviewMark(
            arrangement=arrangement,
            event_index=event_index,
            source_start_seconds=source_start_seconds,
            midi=midi,
            string_index=string_index,
            fret=fret,
            state=state,
            scope=scope,
            marked_at=datetime.now(timezone.utc),
        )
    )
    marks.sort(key=lambda m: (m.arrangement, m.source_start_seconds, m.event_index))
    layer = HumanNoteReviewLayer(
        source_sha256=source_sha256,
        fanout_manifest_path=fanout_manifest_path,
        fanout_manifest_sha256=fanout_manifest_sha256,
        marks=marks,
    )
    path = project / REVIEW_MARKS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(layer.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return layer


def clear_event_mark(project_dir: Path, *, source_sha256: str, arrangement: str, event_index: int) -> HumanNoteReviewLayer:
    project = project_dir.resolve()
    current = load_current_human_review_layer(project, source_sha256)
    marks = [] if current is None else [m for m in current.marks if not (m.arrangement == arrangement and m.event_index == event_index)]
    layer = HumanNoteReviewLayer(
        source_sha256=source_sha256,
        fanout_manifest_path=None if current is None else current.fanout_manifest_path,
        fanout_manifest_sha256=None if current is None else current.fanout_manifest_sha256,
        marks=marks,
    )
    path = project / REVIEW_MARKS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(layer.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return layer
