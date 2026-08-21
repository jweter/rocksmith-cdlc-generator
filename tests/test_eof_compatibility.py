from __future__ import annotations

from pathlib import Path

import pytest

from rocksmith_cdlc_generator.eof_compatibility import (
    EOFCompatibilityFixture,
    compare_imported_source_to_eof_fixture,
)
from rocksmith_cdlc_generator.source_import import (
    ImportedSource,
    SourceNoteEvent,
    SourceProvenance,
    SourceTrack,
)

_FIXTURE = Path(__file__).parent / "fixtures" / "eof" / "synthetic-gp5-reference.json"
_SCORE_SHA = "a" * 64


def _source(*, tuning: list[int] | None = None) -> ImportedSource:
    return ImportedSource(
        provenance=SourceProvenance(
            source_type="guitar_pro",
            source_filename="synthetic.gp5",
            source_sha256=_SCORE_SHA,
            importer="test",
            importer_version="1",
        ),
        tracks=[
            SourceTrack(
                source_track_index=2,
                name="Synthetic Bass",
                instrument="bass",
                tuning_midi=tuning if tuning is not None else [28, 33, 38, 43],
                notes=[
                    SourceNoteEvent(
                        start_seconds=0.5,
                        duration_seconds=0.25,
                        midi=28,
                        string_index=0,
                        fret=0,
                        techniques=["palm_mute"],
                        import_confidence=1.0,
                    ),
                    SourceNoteEvent(
                        start_seconds=1.0,
                        duration_seconds=0.5,
                        midi=35,
                        string_index=1,
                        fret=2,
                        techniques=["vibrato", "slide"],
                        import_confidence=1.0,
                    ),
                ],
            )
        ],
    )


def test_synthetic_reference_matches_tuning_positions_timing_and_techniques() -> None:
    fixture = EOFCompatibilityFixture.read_json(_FIXTURE)

    report = compare_imported_source_to_eof_fixture(_source(), fixture)

    assert report.matched is True
    assert report.mismatches == []


def test_report_preserves_independent_discrepancies_without_mutating_source() -> None:
    fixture = EOFCompatibilityFixture.read_json(_FIXTURE)
    source = _source(tuning=[28, 33, 38, 44])
    source.tracks[0].notes[0].fret = 1
    source.tracks[0].notes[1].start_seconds = 1.01
    source.tracks[0].notes[1].techniques = ["slide"]

    report = compare_imported_source_to_eof_fixture(source, fixture)

    assert report.matched is False
    assert [(item.field, item.event_index) for item in report.mismatches] == [
        ("tuning_midi", None),
        ("note_position", 0),
        ("note_timing", 1),
        ("note_techniques", 1),
    ]
    assert source.tracks[0].notes[0].fret == 1
    assert source.tracks[0].notes[1].techniques == ["slide"]


def test_timing_tolerance_is_explicit_and_deterministic() -> None:
    fixture = EOFCompatibilityFixture.read_json(_FIXTURE)
    source = _source()
    source.tracks[0].notes[0].start_seconds += 5e-7

    assert compare_imported_source_to_eof_fixture(source, fixture).matched is True
    assert (
        compare_imported_source_to_eof_fixture(
            source,
            fixture,
            timing_tolerance_seconds=1e-8,
        ).mismatches[0].field
        == "note_timing"
    )


def test_stale_or_wrong_score_fixture_fails_closed() -> None:
    fixture = EOFCompatibilityFixture.read_json(_FIXTURE)
    source = _source()
    source.provenance.source_sha256 = "b" * 64

    with pytest.raises(ValueError, match="stale or belongs to a different score"):
        compare_imported_source_to_eof_fixture(source, fixture)


def test_fixture_rejects_unsupported_technique_evidence() -> None:
    fixture = EOFCompatibilityFixture.read_json(_FIXTURE)
    payload = fixture.model_dump(mode="json")
    payload["notes"][0]["techniques"] = ["unsupported-eof-only-technique"]

    with pytest.raises(ValueError, match="project-supported techniques"):
        EOFCompatibilityFixture.model_validate(payload)
