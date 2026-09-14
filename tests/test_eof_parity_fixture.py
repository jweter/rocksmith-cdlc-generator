from __future__ import annotations

import pytest

from rocksmith_cdlc_generator.eof_parity_fixture import parse_eof_parity_fixture


def _fixture() -> dict[str, object]:
    return {
        "schema_version": 1,
        "fixture_id": "synthetic-leading-rests-v1",
        "source_kind": "synthetic",
        "arrangement": "bass",
        "beat_times_seconds": [0.0, 0.5, 1.0, 1.5],
        "notes": [
            {
                "onset_seconds": 1.0,
                "duration_seconds": 0.4,
                "string": 0,
                "fret": 3,
                "techniques": [],
            }
        ],
    }


def test_parse_media_safe_fixture() -> None:
    fixture = parse_eof_parity_fixture(_fixture())

    assert fixture.fixture_id == "synthetic-leading-rests-v1"
    assert fixture.arrangement == "bass"
    assert fixture.beat_times_seconds == (0.0, 0.5, 1.0, 1.5)
    assert fixture.notes[0].onset_seconds == 1.0
    assert fixture.notes[0].fret == 3


def test_rejects_private_or_media_path_fields() -> None:
    payload = _fixture()
    payload["audio_path"] = r"C:\private\song.wav"

    with pytest.raises(ValueError, match="forbidden media/private path fields"):
        parse_eof_parity_fixture(payload)


def test_rejects_unknown_top_level_fields() -> None:
    payload = _fixture()
    payload["artist"] = "commercial metadata"

    with pytest.raises(ValueError, match="unsupported fields"):
        parse_eof_parity_fixture(payload)


def test_rejects_nonincreasing_beat_map() -> None:
    payload = _fixture()
    payload["beat_times_seconds"] = [0.0, 0.5, 0.5]

    with pytest.raises(ValueError, match="strictly increasing"):
        parse_eof_parity_fixture(payload)


def test_rejects_nonfinite_note_time() -> None:
    payload = _fixture()
    notes = list(payload["notes"])  # type: ignore[arg-type]
    note = dict(notes[0])
    note["onset_seconds"] = float("inf")
    payload["notes"] = [note]

    with pytest.raises(ValueError, match="finite and non-negative"):
        parse_eof_parity_fixture(payload)


def test_preserves_bass_lead_rhythm_as_explicit_roles() -> None:
    for role in ("bass", "lead", "rhythm"):
        payload = _fixture()
        payload["arrangement"] = role
        assert parse_eof_parity_fixture(payload).arrangement == role


def test_rejects_untracked_arrangement_role() -> None:
    payload = _fixture()
    payload["arrangement"] = "combo"

    with pytest.raises(ValueError, match="bass, lead, or rhythm"):
        parse_eof_parity_fixture(payload)
