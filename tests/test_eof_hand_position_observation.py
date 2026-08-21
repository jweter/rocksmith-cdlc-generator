from __future__ import annotations

import pytest
from pydantic import ValidationError

from rocksmith_cdlc_generator.eof_hand_position_observation import (
    EOFHandPositionFixture,
    EOFHandPositionObservation,
    validate_eof_hand_position_fixture,
)
from rocksmith_cdlc_generator.source_import import (
    ImportedSource,
    SourceNoteEvent,
    SourceProvenance,
    SourceTrack,
)


def _source(*, digest: str = "a" * 64, source_type: str = "gp5") -> ImportedSource:
    return ImportedSource(
        provenance=SourceProvenance(
            source_type=source_type,
            source_filename="synthetic.gp5",
            source_sha256=digest,
            importer="test",
            importer_version="1",
        ),
        tracks=[
            SourceTrack(
                source_track_index=3,
                name="Lead",
                instrument="lead",
                tuning_midi=[40, 45, 50, 55, 59, 64],
                notes=[
                    SourceNoteEvent(
                        start_seconds=0.5,
                        duration_seconds=0.25,
                        midi=64,
                        note_name="E4",
                        string_index=5,
                        fret=0,
                    ),
                    SourceNoteEvent(
                        start_seconds=1.0,
                        duration_seconds=0.25,
                        midi=67,
                        note_name="G4",
                        string_index=5,
                        fret=3,
                    ),
                ],
            )
        ],
    )


def _fixture(**updates: object) -> EOFHandPositionFixture:
    values: dict[str, object] = {
        "fixture_id": "synthetic-lead-eof-hand-position",
        "score_sha256": "a" * 64,
        "score_format": "gp5",
        "source_track_index": 3,
        "eof_version": "reference-build",
        "evidence_note": "Synthetic observation used only to test the evidence contract.",
        "observations": [
            EOFHandPositionObservation(start_seconds=0.0, fret=1),
            EOFHandPositionObservation(start_seconds=0.75, fret=3, source_event_index=1),
        ],
    }
    values.update(updates)
    return EOFHandPositionFixture(**values)


def test_validates_source_bound_hand_position_evidence_without_mutating_source() -> None:
    source = _source()
    before = source.model_dump(mode="json")

    status = validate_eof_hand_position_fixture(source, _fixture())

    assert status.fixture_id == "synthetic-lead-eof-hand-position"
    assert status.source_track_index == 3
    assert status.observation_count == 2
    assert source.model_dump(mode="json") == before


def test_rejects_stale_score_identity() -> None:
    with pytest.raises(ValueError, match="stale or belongs to a different score"):
        validate_eof_hand_position_fixture(_source(), _fixture(score_sha256="b" * 64))


def test_rejects_wrong_score_format() -> None:
    with pytest.raises(ValueError, match="score format does not match"):
        validate_eof_hand_position_fixture(_source(), _fixture(score_format="gp4"))


def test_rejects_missing_source_track() -> None:
    with pytest.raises(ValueError, match="source track is not present"):
        validate_eof_hand_position_fixture(_source(), _fixture(source_track_index=99))


def test_rejects_event_reference_that_no_longer_exists() -> None:
    fixture = _fixture(
        observations=[
            EOFHandPositionObservation(start_seconds=0.0, fret=1, source_event_index=2)
        ]
    )
    with pytest.raises(ValueError, match="source event that no longer exists"):
        validate_eof_hand_position_fixture(_source(), fixture)


def test_rejects_duplicate_or_out_of_order_observation_times() -> None:
    with pytest.raises(ValidationError, match="strictly increasing start times"):
        _fixture(
            observations=[
                EOFHandPositionObservation(start_seconds=1.0, fret=5),
                EOFHandPositionObservation(start_seconds=1.0, fret=7),
            ]
        )
