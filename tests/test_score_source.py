from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from rocksmith_cdlc_generator.score_source import (
    ArrangementRole,
    ProjectScoreSource,
    ScoreArrangementMapping,
    ScoreTrackCandidate,
)


def _tracks() -> list[ScoreTrackCandidate]:
    return [
        ScoreTrackCandidate(
            source_track_index=0,
            name="Lead Guitar",
            instrument_hint="guitar",
            tuning_midi=[40, 45, 50, 55, 59, 64],
            note_count=400,
        ),
        ScoreTrackCandidate(
            source_track_index=1,
            name="Rhythm Guitar",
            instrument_hint="guitar",
            tuning_midi=[40, 45, 50, 55, 59, 64],
            note_count=600,
        ),
        ScoreTrackCandidate(
            source_track_index=2,
            name="Bass",
            instrument_hint="bass",
            tuning_midi=[28, 33, 38, 43],
            note_count=350,
        ),
    ]


def test_complete_score_can_map_bass_lead_and_rhythm_once(tmp_path: Path) -> None:
    score = ProjectScoreSource(
        source_filename="song.gp5",
        source_sha256="a" * 64,
        source_format="gp5",
        imported_relative_path="sources/scores/song.json",
        tracks=_tracks(),
        arrangement_mappings=[
            ScoreArrangementMapping(
                role=ArrangementRole.lead,
                source_track_index=0,
                confidence=0.96,
                basis=["track name contains lead", "six-string guitar tuning"],
            ),
            ScoreArrangementMapping(
                role=ArrangementRole.rhythm,
                source_track_index=1,
                confidence=0.98,
                basis=["track name contains rhythm", "six-string guitar tuning"],
            ),
            ScoreArrangementMapping(
                role=ArrangementRole.bass,
                source_track_index=2,
                confidence=1.0,
                basis=["track name contains bass", "four-string bass tuning"],
            ),
        ],
    )

    destination = score.write_json(tmp_path / "score_source.json")
    restored = ProjectScoreSource.read_json(destination)

    assert restored.mapping_for(ArrangementRole.bass).source_track_index == 2
    assert restored.mapping_for(ArrangementRole.lead).source_track_index == 0
    assert restored.mapping_for(ArrangementRole.rhythm).source_track_index == 1
    assert restored.mapping_for(ArrangementRole.lead).requires_human_review is True
    assert restored.mapping_for(ArrangementRole.bass).requires_human_review is True


def test_exact_confidence_proposal_still_requires_human_confirmation() -> None:
    mapping = ScoreArrangementMapping(
        role=ArrangementRole.bass,
        source_track_index=2,
        confidence=1.0,
        basis=["track name contains bass", "four-string bass tuning"],
    )

    assert mapping.human_confirmed is False
    assert mapping.requires_human_review is True


def test_human_confirmation_clears_mapping_review_gate() -> None:
    mapping = ScoreArrangementMapping(
        role=ArrangementRole.lead,
        source_track_index=0,
        confidence=0.7,
        basis=["best available guitar candidate"],
        human_confirmed=True,
    )

    assert mapping.requires_human_review is False


def test_score_rejects_mapping_to_unknown_track() -> None:
    with pytest.raises(ValidationError, match="unknown score track 9"):
        ProjectScoreSource(
            source_filename="song.musicxml",
            source_sha256="b" * 64,
            source_format="musicxml",
            imported_relative_path="sources/scores/song.json",
            tracks=_tracks(),
            arrangement_mappings=[
                ScoreArrangementMapping(
                    role=ArrangementRole.bass,
                    source_track_index=9,
                    confidence=1.0,
                )
            ],
        )


def test_score_rejects_duplicate_arrangement_role() -> None:
    with pytest.raises(ValidationError, match="multiple mappings for lead"):
        ProjectScoreSource(
            source_filename="song.mxl",
            source_sha256="c" * 64,
            source_format="mxl",
            imported_relative_path="sources/scores/song.json",
            tracks=_tracks(),
            arrangement_mappings=[
                ScoreArrangementMapping(
                    role=ArrangementRole.lead,
                    source_track_index=0,
                    confidence=1.0,
                ),
                ScoreArrangementMapping(
                    role=ArrangementRole.lead,
                    source_track_index=1,
                    confidence=1.0,
                ),
            ],
        )
