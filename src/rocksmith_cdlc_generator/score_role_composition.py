from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .score_source import ArrangementRole, ProjectScoreSource


class ScoreRoleCompositionSelection(BaseModel):
    """Ordered human-selected score tracks contributing to one Rocksmith role."""

    model_config = ConfigDict(frozen=True)

    role: ArrangementRole
    source_track_indices: list[int] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_tracks(self) -> "ScoreRoleCompositionSelection":
        if len(self.source_track_indices) != len(set(self.source_track_indices)):
            raise ValueError("score role composition cannot include the same source track twice")
        if any(index < 0 for index in self.source_track_indices):
            raise ValueError("score role composition track indexes must be non-negative")
        return self


class ScoreRoleCompositionPlan(BaseModel):
    """Provenance-bound, ordered multi-track composition intent for a complete score.

    This contract records composition intent only. It does not merge note streams or
    grant timing, fingering, technique, chord, tone, validation, or export authority.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: int = 1
    score_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    score_format: str
    selections: list[ScoreRoleCompositionSelection] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_roles(self) -> "ScoreRoleCompositionPlan":
        roles = [selection.role for selection in self.selections]
        if len(roles) != len(set(roles)):
            raise ValueError("score role composition contains duplicate arrangement roles")
        return self

    def selection_for(self, role: ArrangementRole) -> ScoreRoleCompositionSelection | None:
        return next((selection for selection in self.selections if selection.role is role), None)


def validate_score_role_composition(
    score: ProjectScoreSource,
    plan: ScoreRoleCompositionPlan,
) -> ScoreRoleCompositionPlan:
    """Fail closed unless a composition plan is current and anchored to confirmed primaries.

    The existing one-track-per-role human mapping remains the primary authority while
    multi-track support is introduced incrementally. Each composed role must therefore
    begin with that exact human-confirmed primary track; any additional ordered tracks
    are explicit additions rather than replacements inferred by the program.
    """

    if plan.score_sha256 != score.source_sha256 or plan.score_format != score.source_format:
        raise ValueError("score role composition is stale for the registered score")

    known_indexes = {track.source_track_index for track in score.tracks}
    for selection in plan.selections:
        unknown = [index for index in selection.source_track_indices if index not in known_indexes]
        if unknown:
            raise ValueError(
                f"{selection.role.value} composition references unknown score track(s): {unknown}"
            )

        mapping = score.mapping_for(selection.role)
        if mapping is None or not mapping.human_confirmed:
            raise ValueError(
                f"{selection.role.value} composition requires a human-confirmed primary mapping"
            )
        if selection.source_track_indices[0] != mapping.source_track_index:
            raise ValueError(
                f"{selection.role.value} composition must keep confirmed track "
                f"{mapping.source_track_index} as its primary first track"
            )

    return plan


def build_score_role_composition_plan(
    score: ProjectScoreSource,
    selections: dict[ArrangementRole, list[int]],
) -> ScoreRoleCompositionPlan:
    """Build and validate explicit ordered composition intent for the current score."""

    plan = ScoreRoleCompositionPlan(
        score_sha256=score.source_sha256,
        score_format=score.source_format,
        selections=[
            ScoreRoleCompositionSelection(role=role, source_track_indices=list(indexes))
            for role, indexes in sorted(selections.items(), key=lambda item: item[0].value)
        ],
    )
    return validate_score_role_composition(score, plan)
