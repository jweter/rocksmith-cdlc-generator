from __future__ import annotations

import pytest

from rocksmith_cdlc_generator.score_role_composition import (
    ScoreRoleCompositionPlan,
    ScoreRoleCompositionSelection,
    build_score_role_composition_plan,
    validate_score_role_composition,
)
from rocksmith_cdlc_generator.score_source import (
    ArrangementRole,
    ProjectScoreSource,
    ScoreArrangementMapping,
    ScoreTrackCandidate,
)


def _score() -> ProjectScoreSource:
    return ProjectScoreSource(
        source_filename="song.gp5",
        source_sha256="a" * 64,
        source_format="gp5",
        imported_relative_path="sources/score/song.gp5",
        tracks=[
            ScoreTrackCandidate(source_track_index=0, name="Lead", instrument_hint="guitar", note_count=100),
            ScoreTrackCandidate(source_track_index=1, name="Solo", instrument_hint="guitar", note_count=30),
            ScoreTrackCandidate(source_track_index=2, name="Rhythm", instrument_hint="guitar", note_count=120),
            ScoreTrackCandidate(source_track_index=3, name="Clean", instrument_hint="guitar", note_count=20),
            ScoreTrackCandidate(source_track_index=4, name="Bass", instrument_hint="bass", note_count=90),
        ],
        arrangement_mappings=[
            ScoreArrangementMapping(role="lead", source_track_index=0, confidence=0.9, human_confirmed=True),
            ScoreArrangementMapping(role="rhythm", source_track_index=2, confidence=0.9, human_confirmed=True),
            ScoreArrangementMapping(role="bass", source_track_index=4, confidence=0.9, human_confirmed=True),
        ],
    )


def test_builds_ordered_multi_track_role_composition() -> None:
    plan = build_score_role_composition_plan(
        _score(),
        {
            ArrangementRole.lead: [0, 1],
            ArrangementRole.rhythm: [2, 3],
            ArrangementRole.bass: [4],
        },
    )

    assert plan.selection_for(ArrangementRole.lead).source_track_indices == [0, 1]
    assert plan.selection_for(ArrangementRole.rhythm).source_track_indices == [2, 3]
    assert plan.score_sha256 == "a" * 64


def test_rejects_duplicate_track_inside_role() -> None:
    with pytest.raises(ValueError, match="same source track twice"):
        ScoreRoleCompositionSelection(role="lead", source_track_indices=[0, 0])


def test_rejects_unknown_extra_track() -> None:
    with pytest.raises(ValueError, match="unknown score track"):
        build_score_role_composition_plan(_score(), {ArrangementRole.lead: [0, 99]})


def test_rejects_unconfirmed_primary_mapping() -> None:
    score = _score()
    mappings = [
        mapping.model_copy(update={"human_confirmed": False}) if mapping.role is ArrangementRole.lead else mapping
        for mapping in score.arrangement_mappings
    ]
    score = score.model_copy(update={"arrangement_mappings": mappings})

    with pytest.raises(ValueError, match="human-confirmed primary mapping"):
        build_score_role_composition_plan(score, {ArrangementRole.lead: [0, 1]})


def test_rejects_reordering_confirmed_primary_behind_extra_track() -> None:
    with pytest.raises(ValueError, match="primary first track"):
        build_score_role_composition_plan(_score(), {ArrangementRole.lead: [1, 0]})


def test_rejects_stale_score_provenance() -> None:
    plan = ScoreRoleCompositionPlan(
        score_sha256="b" * 64,
        score_format="gp5",
        selections=[ScoreRoleCompositionSelection(role="lead", source_track_indices=[0, 1])],
    )

    with pytest.raises(ValueError, match="stale for the registered score"):
        validate_score_role_composition(_score(), plan)
