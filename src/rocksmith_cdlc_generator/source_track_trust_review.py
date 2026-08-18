from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .hashing import sha256_file
from .score_fanout import ScoreFanoutEntry, ScoreFanoutManifest
from .score_mapping_review import load_score_for_mapping_review, score_mapping_transaction
from .source_import import ImportedSource, SourceTrustClass

ArrangementRoleName = Literal["bass", "lead", "rhythm"]
_ACCEPTED_SYMBOLIC_TRUST = {
    SourceTrustClass.symbolic_unverified,
    SourceTrustClass.symbolic_verified,
}
TRACK_SOURCE_TRUST_REVIEW_PATH = Path("review") / "source_track_trust.json"


class TrackSourceTrustAcceptance(BaseModel):
    """Human acceptance of exact imported note identity/positions for one score track."""

    model_config = ConfigDict(frozen=True)

    arrangement: ArrangementRoleName
    source_track_index: int = Field(ge=0)
    source_track_name: str | None = None
    output_json: str
    output_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    note_count: int = Field(gt=0)
    accepted_scope: Literal["imported_note_identity_and_positions"] = (
        "imported_note_identity_and_positions"
    )
    accepted_at: datetime


class TrackSourceTrustReviewLayer(BaseModel):
    """Provenance-bearing track review bound to one exact current score fan-out."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    score_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    score_format: str
    fanout_manifest_path: str
    fanout_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    acceptances: list[TrackSourceTrustAcceptance] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_arrangements(self) -> "TrackSourceTrustReviewLayer":
        roles = [item.arrangement for item in self.acceptances]
        if len(roles) != len(set(roles)):
            raise ValueError("source track trust review contains duplicate arrangement acceptances")
        return self

    def acceptance_for(self, arrangement: ArrangementRoleName) -> TrackSourceTrustAcceptance | None:
        return next(
            (item for item in self.acceptances if item.arrangement == arrangement),
            None,
        )


def _project(project_dir: Path) -> Path:
    project = project_dir.expanduser().resolve()
    if not (project / "project.json").is_file():
        raise FileNotFoundError(f"Not a CDLC project: {project}")
    return project


def _current_fanout_locked(project: Path) -> tuple[Path, ScoreFanoutManifest]:
    score = load_score_for_mapping_review(project)
    path = project / "sources" / "imported" / f"score-fanout-{score.source_sha256[:12]}.json"
    if not path.is_file():
        raise FileNotFoundError("Current score fan-out manifest is not available")
    manifest = ScoreFanoutManifest.model_validate_json(path.read_text(encoding="utf-8"))
    if (
        manifest.score_source_sha256 != score.source_sha256
        or manifest.score_source_format != score.source_format
    ):
        raise ValueError("Current score fan-out does not match the registered score")
    return path, manifest


def _entry_for_locked(
    project: Path,
    arrangement: ArrangementRoleName,
) -> tuple[Path, ScoreFanoutEntry, ImportedSource]:
    score = load_score_for_mapping_review(project)
    _fanout_path, manifest = _current_fanout_locked(project)
    entry = next((item for item in manifest.arrangements if item.role.value == arrangement), None)
    if entry is None:
        raise ValueError(f"Current score fan-out has no {arrangement} arrangement")
    mapping = score.mapping_for(entry.role)
    if (
        mapping is None
        or not mapping.human_confirmed
        or mapping.source_track_index != entry.source_track_index
    ):
        raise ValueError(f"{arrangement} score mapping is no longer human-confirmed/current")

    output = (project / entry.output_json).resolve()
    if not output.is_relative_to(project) or not output.is_file():
        raise ValueError(f"{arrangement} fan-out source is not a safe project-local file")
    imported = ImportedSource.read_json(output)
    if imported.provenance.source_sha256 != score.source_sha256:
        raise ValueError(f"{arrangement} fan-out provenance does not match the registered score")
    if len(imported.tracks) != 1:
        raise ValueError(f"{arrangement} fan-out must contain exactly one source track")
    track = imported.tracks[0]
    if track.source_track_index != entry.source_track_index or track.instrument != arrangement:
        raise ValueError(f"{arrangement} fan-out source no longer matches current authority")
    return output, entry, imported


def _validate_track_position_scope(imported: ImportedSource, arrangement: ArrangementRoleName) -> None:
    track = imported.tracks[0]
    if track.tuning_midi is None:
        raise ValueError(f"{arrangement} track trust review requires explicit source tuning")
    if not track.notes:
        raise ValueError(f"{arrangement} track trust review requires at least one source note")

    for index, note in enumerate(track.notes):
        if note.trust_class not in _ACCEPTED_SYMBOLIC_TRUST:
            raise ValueError(
                f"{arrangement} event {index} is not an imported symbolic source fact"
            )
        if note.string_index is None or note.fret is None:
            raise ValueError(
                f"{arrangement} event {index} has no explicit string/fret position; "
                "track acceptance cannot manufacture one"
            )
        if note.string_index >= len(track.tuning_midi):
            raise ValueError(f"{arrangement} event {index} string index is outside source tuning")
        if int(track.tuning_midi[note.string_index]) + note.fret != note.midi:
            raise ValueError(
                f"{arrangement} event {index} string/fret position does not produce source MIDI pitch"
            )


def _validate_acceptance_locked(
    project: Path,
    acceptance: TrackSourceTrustAcceptance,
) -> None:
    output, entry, imported = _entry_for_locked(project, acceptance.arrangement)
    track = imported.tracks[0]
    if acceptance.source_track_index != entry.source_track_index:
        raise ValueError("Track source trust acceptance points at a stale source track")
    expected_relative = output.relative_to(project).as_posix()
    if acceptance.output_json != expected_relative:
        raise ValueError("Track source trust acceptance points at a stale fan-out output")
    if acceptance.output_sha256 != sha256_file(output):
        raise ValueError("Track source trust acceptance is stale for current fan-out content")
    if acceptance.note_count != len(track.notes):
        raise ValueError("Track source trust acceptance note count is stale")
    if acceptance.source_track_name != track.name:
        raise ValueError("Track source trust acceptance track name is stale")
    _validate_track_position_scope(imported, acceptance.arrangement)


def _load_current_locked(project: Path) -> TrackSourceTrustReviewLayer | None:
    review_path = project / TRACK_SOURCE_TRUST_REVIEW_PATH
    if not review_path.is_file():
        return None
    score = load_score_for_mapping_review(project)
    fanout_path, _manifest = _current_fanout_locked(project)
    layer = TrackSourceTrustReviewLayer.model_validate_json(
        review_path.read_text(encoding="utf-8")
    )
    if layer.score_sha256 != score.source_sha256 or layer.score_format != score.source_format:
        raise ValueError("Track source trust review is stale for the registered score")
    expected_relative = fanout_path.relative_to(project).as_posix()
    if layer.fanout_manifest_path != expected_relative:
        raise ValueError("Track source trust review points at a stale score fan-out")
    if layer.fanout_manifest_sha256 != sha256_file(fanout_path):
        raise ValueError("Track source trust review is stale for the current score fan-out")
    for acceptance in layer.acceptances:
        _validate_acceptance_locked(project, acceptance)
    return layer


def load_current_track_source_trust_review(
    project_dir: Path,
) -> TrackSourceTrustReviewLayer | None:
    """Load current track acceptance, failing closed on any provenance/content drift."""

    project = _project(project_dir)
    with score_mapping_transaction(project):
        return _load_current_locked(project)


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def record_track_source_trust_acceptance(
    project_dir: Path,
    *,
    arrangement: ArrangementRoleName,
) -> TrackSourceTrustReviewLayer:
    """Accept exact imported note identity/positions for one current source track.

    This records human provenance only. It does not mutate fan-out bytes, clear event
    review flags, accept timing/techniques/chords, or create missing positions. A later
    consumer may use this evidence only for the explicit acceptance scope recorded here.
    """

    project = _project(project_dir)
    with score_mapping_transaction(project):
        score = load_score_for_mapping_review(project)
        fanout_path, _manifest = _current_fanout_locked(project)
        output, entry, imported = _entry_for_locked(project, arrangement)
        _validate_track_position_scope(imported, arrangement)
        track = imported.tracks[0]

        current = _load_current_locked(project)
        acceptances = [] if current is None else list(current.acceptances)
        acceptances = [item for item in acceptances if item.arrangement != arrangement]
        acceptances.append(
            TrackSourceTrustAcceptance(
                arrangement=arrangement,
                source_track_index=entry.source_track_index,
                source_track_name=track.name,
                output_json=output.relative_to(project).as_posix(),
                output_sha256=sha256_file(output),
                note_count=len(track.notes),
                accepted_at=datetime.now(timezone.utc),
            )
        )
        role_order = {"lead": 0, "rhythm": 1, "bass": 2}
        acceptances.sort(key=lambda item: role_order[item.arrangement])
        layer = TrackSourceTrustReviewLayer(
            score_sha256=score.source_sha256,
            score_format=score.source_format,
            fanout_manifest_path=fanout_path.relative_to(project).as_posix(),
            fanout_manifest_sha256=sha256_file(fanout_path),
            acceptances=acceptances,
        )
        _atomic_write(
            project / TRACK_SOURCE_TRUST_REVIEW_PATH,
            layer.model_dump_json(indent=2) + "\n",
        )
        return layer
