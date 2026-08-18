from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .score_fanout import ScoreFanoutManifest
from .score_mapping_review import load_score_for_mapping_review
from .source_import import ImportedSource, SourceTrustClass
from .source_track_trust_review import (
    TRACK_SOURCE_TRUST_REVIEW_PATH,
    load_current_track_source_trust_review,
)

TrackTrustState = Literal["unreviewed", "current", "stale"]
_ACCEPTED_SYMBOLIC_TRUST = {
    SourceTrustClass.symbolic_unverified,
    SourceTrustClass.symbolic_verified,
}


class TrackTrustWorkspaceItem(BaseModel):
    """Read-only Song Workspace status for one current Bass/Lead/Rhythm source track."""

    model_config = ConfigDict(frozen=True)

    arrangement: Literal["bass", "lead", "rhythm"]
    source_track_index: int = Field(ge=0)
    source_track_name: str | None = None
    note_count: int = Field(ge=0)
    review_state: TrackTrustState
    acceptance_scope: Literal["imported_note_identity_and_positions"] = (
        "imported_note_identity_and_positions"
    )
    can_accept: bool
    blockers: list[str] = Field(default_factory=list)


class TrackTrustWorkspaceStatus(BaseModel):
    """Read-only control model for explicit track source-trust review in Song Workspace."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = 1
    stale_review_detail: str | None = None
    tracks: list[TrackTrustWorkspaceItem] = Field(default_factory=list)


def _project(project_dir: Path) -> Path:
    project = project_dir.expanduser().resolve()
    if not (project / "project.json").is_file():
        raise FileNotFoundError(f"Not a CDLC project: {project}")
    return project


def _current_manifest(project: Path) -> ScoreFanoutManifest:
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
    return manifest


def _eligibility_blockers(imported: ImportedSource, arrangement: str) -> list[str]:
    if len(imported.tracks) != 1:
        return [f"{arrangement} fan-out must contain exactly one source track"]
    track = imported.tracks[0]
    blockers: list[str] = []
    if track.tuning_midi is None:
        blockers.append("explicit source tuning is required")
    if not track.notes:
        blockers.append("at least one source note is required")
        return blockers

    missing_positions = 0
    pitch_conflicts = 0
    non_symbolic = 0
    for note in track.notes:
        if note.trust_class not in _ACCEPTED_SYMBOLIC_TRUST:
            non_symbolic += 1
        if note.string_index is None or note.fret is None:
            missing_positions += 1
            continue
        if track.tuning_midi is None or note.string_index >= len(track.tuning_midi):
            pitch_conflicts += 1
            continue
        if int(track.tuning_midi[note.string_index]) + note.fret != note.midi:
            pitch_conflicts += 1

    if non_symbolic:
        blockers.append(f"{non_symbolic} event(s) are not imported symbolic source facts")
    if missing_positions:
        blockers.append(f"{missing_positions} event(s) have unresolved string/fret positions")
    if pitch_conflicts:
        blockers.append(f"{pitch_conflicts} event(s) have position/pitch conflicts")
    return blockers


def inspect_track_trust_workspace_status(project_dir: Path) -> TrackTrustWorkspaceStatus:
    """Describe current whole-track trust-review controls without granting authority.

    A stale/corrupt review layer is surfaced as stale rather than silently ignored. The
    current fan-out is still independently inspected so Song Workspace can explain
    whether explicit reacceptance is currently possible. This function never records an
    acceptance, changes imported trust, clears event review, or mutates project files.
    """

    project = _project(project_dir)
    score = load_score_for_mapping_review(project)
    manifest = _current_manifest(project)

    stale_detail: str | None = None
    try:
        review_layer = load_current_track_source_trust_review(project)
    except (OSError, ValueError) as exc:
        review_layer = None
        if (project / TRACK_SOURCE_TRUST_REVIEW_PATH).is_file():
            stale_detail = str(exc)

    role_order = {"lead": 0, "rhythm": 1, "bass": 2}
    items: list[TrackTrustWorkspaceItem] = []
    for entry in sorted(manifest.arrangements, key=lambda item: role_order[item.role.value]):
        role = entry.role.value
        mapping = score.mapping_for(entry.role)
        if (
            mapping is None
            or not mapping.human_confirmed
            or mapping.source_track_index != entry.source_track_index
        ):
            raise ValueError(f"{role} score mapping is no longer human-confirmed/current")

        output = (project / entry.output_json).resolve()
        if not output.is_relative_to(project) or not output.is_file():
            raise ValueError(f"{role} fan-out source is not a safe project-local file")
        imported = ImportedSource.read_json(output)
        if imported.provenance.source_sha256 != score.source_sha256:
            raise ValueError(f"{role} fan-out provenance does not match the registered score")
        if len(imported.tracks) != 1:
            raise ValueError(f"{role} fan-out must contain exactly one source track")
        track = imported.tracks[0]
        if track.source_track_index != entry.source_track_index or track.instrument != role:
            raise ValueError(f"{role} fan-out source no longer matches current authority")

        acceptance = review_layer.acceptance_for(role) if review_layer is not None else None
        review_state: TrackTrustState
        if acceptance is not None:
            review_state = "current"
        elif stale_detail is not None:
            review_state = "stale"
        else:
            review_state = "unreviewed"

        blockers = _eligibility_blockers(imported, role)
        items.append(
            TrackTrustWorkspaceItem(
                arrangement=role,
                source_track_index=entry.source_track_index,
                source_track_name=track.name,
                note_count=len(track.notes),
                review_state=review_state,
                can_accept=not blockers,
                blockers=blockers,
            )
        )

    return TrackTrustWorkspaceStatus(stale_review_detail=stale_detail, tracks=items)
