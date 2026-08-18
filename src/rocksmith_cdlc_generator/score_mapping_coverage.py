from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .score_source import ArrangementRole, ProjectScoreSource


_PLAYABLE_HINTS = {"bass", "guitar"}
_ROLE_ORDER = {
    ArrangementRole.lead: 0,
    ArrangementRole.rhythm: 1,
    ArrangementRole.bass: 2,
}


class RoleMappingCoverage(BaseModel):
    """Read-only summary of the current single-track mapping for one role."""

    model_config = ConfigDict(frozen=True)

    role: ArrangementRole
    source_track_index: int | None = Field(default=None, ge=0)
    source_track_name: str | None = None
    human_confirmed: bool = False


class UnmappedPlayableTrack(BaseModel):
    """A score track that looks playable but is not referenced by any role mapping."""

    model_config = ConfigDict(frozen=True)

    source_track_index: int = Field(ge=0)
    name: str | None = None
    instrument_hint: str
    note_count: int = Field(gt=0)
    tuning_midi: tuple[int, ...] | None = None


class ScoreMappingCoverage(BaseModel):
    """Informational coverage view for detecting possible single-track content loss."""

    model_config = ConfigDict(frozen=True)

    schema_version: int = 1
    roles: tuple[RoleMappingCoverage, ...]
    unmapped_playable_tracks: tuple[UnmappedPlayableTrack, ...] = ()

    @property
    def has_unmapped_playable_material(self) -> bool:
        return bool(self.unmapped_playable_tracks)


def summarize_score_mapping_coverage(score: ProjectScoreSource) -> ScoreMappingCoverage:
    """Expose playable score tracks that the current role mappings do not reference.

    This is deliberately conservative and read-only. A track is surfaced only when the
    score inventory already gave it an explicit playable ``instrument_hint`` (``bass``
    or ``guitar``) and it contains pitched notes. The summary never assigns the track to
    Bass/Lead/Rhythm and never changes human mapping authority.
    """

    tracks_by_index = {track.source_track_index: track for track in score.tracks}
    referenced_indexes = {
        mapping.source_track_index for mapping in score.arrangement_mappings
    }

    roles: list[RoleMappingCoverage] = []
    for role in sorted(ArrangementRole, key=lambda item: _ROLE_ORDER[item]):
        mapping = score.mapping_for(role)
        if mapping is None:
            roles.append(RoleMappingCoverage(role=role))
            continue
        track = tracks_by_index[mapping.source_track_index]
        roles.append(
            RoleMappingCoverage(
                role=role,
                source_track_index=track.source_track_index,
                source_track_name=track.name,
                human_confirmed=mapping.human_confirmed,
            )
        )

    extras = [
        UnmappedPlayableTrack(
            source_track_index=track.source_track_index,
            name=track.name,
            instrument_hint=track.instrument_hint,
            note_count=track.note_count,
            tuning_midi=(tuple(track.tuning_midi) if track.tuning_midi is not None else None),
        )
        for track in score.tracks
        if track.source_track_index not in referenced_indexes
        and track.note_count > 0
        and track.instrument_hint in _PLAYABLE_HINTS
    ]
    extras.sort(key=lambda item: item.source_track_index)

    return ScoreMappingCoverage(
        roles=tuple(roles),
        unmapped_playable_tracks=tuple(extras),
    )
