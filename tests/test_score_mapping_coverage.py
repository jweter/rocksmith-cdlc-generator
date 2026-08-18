from __future__ import annotations

from rocksmith_cdlc_generator.score_mapping_coverage import summarize_score_mapping_coverage
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
            ScoreTrackCandidate(
                source_track_index=0,
                name="James Rhythm",
                instrument_hint="guitar",
                tuning_midi=[40, 45, 50, 55, 59, 64],
                note_count=500,
            ),
            ScoreTrackCandidate(
                source_track_index=1,
                name="Kirk Lead",
                instrument_hint="guitar",
                tuning_midi=[40, 45, 50, 55, 59, 64],
                note_count=420,
            ),
            ScoreTrackCandidate(
                source_track_index=2,
                name="Bass",
                instrument_hint="bass",
                tuning_midi=[28, 33, 38, 43],
                note_count=390,
            ),
            ScoreTrackCandidate(
                source_track_index=3,
                name="Clean Guitar",
                instrument_hint="guitar",
                tuning_midi=[40, 45, 50, 55, 59, 64],
                note_count=64,
            ),
            ScoreTrackCandidate(
                source_track_index=4,
                name="Solo",
                instrument_hint="guitar",
                tuning_midi=[40, 45, 50, 55, 59, 64],
                note_count=81,
            ),
            ScoreTrackCandidate(
                source_track_index=5,
                name="Drums",
                instrument_hint=None,
                tuning_midi=[35, 38, 42, 46],
                note_count=700,
            ),
        ],
        arrangement_mappings=[
            ScoreArrangementMapping(
                role=ArrangementRole.rhythm,
                source_track_index=0,
                confidence=0.99,
                basis=["human selected score track explicitly"],
                human_confirmed=True,
            ),
            ScoreArrangementMapping(
                role=ArrangementRole.lead,
                source_track_index=1,
                confidence=0.99,
                basis=["human selected score track explicitly"],
                human_confirmed=True,
            ),
            ScoreArrangementMapping(
                role=ArrangementRole.bass,
                source_track_index=2,
                confidence=0.99,
                basis=["human selected score track explicitly"],
                human_confirmed=True,
            ),
        ],
    )


def test_surfaces_unmapped_playable_tracks_without_assigning_them() -> None:
    coverage = summarize_score_mapping_coverage(_score())

    assert [role.role for role in coverage.roles] == [
        ArrangementRole.lead,
        ArrangementRole.rhythm,
        ArrangementRole.bass,
    ]
    assert all(role.human_confirmed for role in coverage.roles)
    assert [track.source_track_index for track in coverage.unmapped_playable_tracks] == [3, 4]
    assert [track.name for track in coverage.unmapped_playable_tracks] == [
        "Clean Guitar",
        "Solo",
    ]
    assert coverage.has_unmapped_playable_material is True


def test_does_not_resurrect_percussion_from_string_like_metadata() -> None:
    coverage = summarize_score_mapping_coverage(_score())

    assert 5 not in {
        track.source_track_index for track in coverage.unmapped_playable_tracks
    }


def test_existing_unconfirmed_mapping_still_counts_as_referenced_not_extra() -> None:
    score = _score()
    score = score.model_copy(
        update={
            "arrangement_mappings": [
                mapping.model_copy(update={"human_confirmed": False})
                if mapping.role is ArrangementRole.lead
                else mapping
                for mapping in score.arrangement_mappings
            ]
        }
    )

    coverage = summarize_score_mapping_coverage(score)

    lead = next(role for role in coverage.roles if role.role is ArrangementRole.lead)
    assert lead.source_track_index == 1
    assert lead.human_confirmed is False
    assert [track.source_track_index for track in coverage.unmapped_playable_tracks] == [3, 4]


def test_missing_role_is_visible_without_guessing_a_replacement() -> None:
    score = _score()
    score = score.model_copy(
        update={
            "arrangement_mappings": [
                mapping
                for mapping in score.arrangement_mappings
                if mapping.role is not ArrangementRole.lead
            ]
        }
    )

    coverage = summarize_score_mapping_coverage(score)

    lead = next(role for role in coverage.roles if role.role is ArrangementRole.lead)
    assert lead.source_track_index is None
    assert lead.source_track_name is None
    assert lead.human_confirmed is False
    assert [track.source_track_index for track in coverage.unmapped_playable_tracks] == [1, 3, 4]
