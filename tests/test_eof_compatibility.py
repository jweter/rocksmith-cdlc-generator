from __future__ import annotations

from pathlib import Path

import pytest

from rocksmith_cdlc_generator.eof_compatibility import (
    EOFCompatibilityFixture,
    compare_imported_source_to_eof_fixture,
)
from rocksmith_cdlc_generator.guitarpro_import import import_guitarpro
from rocksmith_cdlc_generator.source_import import ImportedSource

_FIXTURE = Path(__file__).parent / "fixtures" / "eof" / "synthetic-gp5-reference.json"
_SCORE = Path(__file__).parent / "fixtures" / "eof" / "synthetic.gp5"


def _source(*, tuning: list[int] | None = None) -> ImportedSource:
    source = import_guitarpro(_SCORE, track_index=0, instrument="bass")
    if tuning is not None:
        source.tracks[0].tuning_midi = tuning
    return source


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


def test_wrong_score_format_fixture_fails_closed() -> None:
    fixture = EOFCompatibilityFixture.read_json(_FIXTURE).model_copy(
        update={"score_format": "gp4"}
    )

    with pytest.raises(ValueError, match="score format does not match"):
        compare_imported_source_to_eof_fixture(_source(), fixture)


def test_fixture_rejects_unsupported_technique_evidence() -> None:
    fixture = EOFCompatibilityFixture.read_json(_FIXTURE)
    payload = fixture.model_dump(mode="json")
    payload["notes"][0]["techniques"] = ["unsupported-eof-only-technique"]

    with pytest.raises(ValueError, match="project-supported techniques"):
        EOFCompatibilityFixture.model_validate(payload)
