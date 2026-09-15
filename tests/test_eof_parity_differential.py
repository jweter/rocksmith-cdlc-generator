from __future__ import annotations

from dataclasses import replace

import pytest

from rocksmith_cdlc_generator.eof_parity_differential import compare_eof_parity_fixtures
from rocksmith_cdlc_generator.eof_parity_fixture import EofParityNote, parse_eof_parity_fixture


def _fixture(*, arrangement: str = "bass"):
    return parse_eof_parity_fixture(
        {
            "schema_version": 1,
            "fixture_id": "synthetic-leading-rests-v1",
            "source_kind": "synthetic",
            "arrangement": arrangement,
            "beat_times_seconds": [0.0, 0.5, 1.0, 1.5],
            "notes": [
                {
                    "onset_seconds": 1.0,
                    "duration_seconds": 0.4,
                    "string": 0,
                    "fret": 3,
                    "techniques": ["palm_mute"],
                }
            ],
        }
    )


def test_identical_fixture_matches() -> None:
    expected = _fixture()

    result = compare_eof_parity_fixtures(expected, expected)

    assert result.matches is True
    assert result.mismatches == ()


def test_small_float_representation_delta_is_tolerated() -> None:
    expected = _fixture()
    actual = replace(expected, beat_times_seconds=(0.0, 0.5000004, 1.0, 1.5))

    result = compare_eof_parity_fixtures(expected, actual, tolerance_seconds=1e-6)

    assert result.matches is True


def test_reports_timing_and_musical_identity_mismatches() -> None:
    expected = _fixture()
    actual_note = EofParityNote(
        onset_seconds=1.02,
        duration_seconds=0.3,
        string=1,
        fret=5,
        techniques=(),
    )
    actual = replace(expected, beat_times_seconds=(0.0, 0.5, 1.1, 1.5), notes=(actual_note,))

    result = compare_eof_parity_fixtures(expected, actual)

    assert result.matches is False
    fields = {mismatch.field for mismatch in result.mismatches}
    assert fields == {
        "beat_times_seconds[2]",
        "notes[0].onset_seconds",
        "notes[0].duration_seconds",
        "notes[0].string",
        "notes[0].fret",
        "notes[0].techniques",
    }


def test_reports_length_mismatch_without_hiding_shared_prefix_differences() -> None:
    expected = _fixture()
    actual = replace(expected, beat_times_seconds=(0.0, 0.6), notes=())

    result = compare_eof_parity_fixtures(expected, actual)

    fields = {mismatch.field for mismatch in result.mismatches}
    assert "beat_times_seconds.length" in fields
    assert "beat_times_seconds[1]" in fields
    assert "notes.length" in fields


def test_bass_lead_rhythm_identity_is_not_interchangeable() -> None:
    result = compare_eof_parity_fixtures(_fixture(arrangement="bass"), _fixture(arrangement="lead"))

    assert result.matches is False
    assert any(mismatch.field == "arrangement" for mismatch in result.mismatches)


def test_rejects_invalid_tolerance() -> None:
    fixture = _fixture()

    with pytest.raises(ValueError, match="finite and non-negative"):
        compare_eof_parity_fixtures(fixture, fixture, tolerance_seconds=float("nan"))
