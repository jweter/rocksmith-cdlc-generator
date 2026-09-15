from __future__ import annotations

import json
from pathlib import Path

from rocksmith_cdlc_generator.deterministic_tempo_map import build_deterministic_tempo_map
from rocksmith_cdlc_generator.eof_parity_differential import compare_eof_parity_fixtures
from rocksmith_cdlc_generator.eof_parity_fixture import parse_eof_parity_fixture
from rocksmith_cdlc_generator.eof_parity_generator_projection import (
    eof_parity_fixture_from_generator_output,
)
from rocksmith_cdlc_generator.reviewed_bass_authoring import (
    ReviewedBassAuthoringInput,
    ReviewedBassAuthoringNote,
)
from rocksmith_cdlc_generator.reviewed_rocksmith_xml import rocksmith_xml_input_from_reviewed_bass
from rocksmith_cdlc_generator.source_import import SourceTrustClass

_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "eof" / "synthetic-parity-bass-v1.json"
_BASS_TUNING_MIDI = (28, 33, 38, 43)


def _expected_fixture():
    payload = json.loads(_FIXTURE_PATH.read_text())
    return parse_eof_parity_fixture(payload)


def _synthetic_bass_authoring_input(*, second_note_fret: int = 2) -> ReviewedBassAuthoringInput:
    """Build the reviewed Bass authoring input for the fixture's synthetic two-note song.

    Constructed directly (no project directory, no recording/score files) since the
    fixture is a synthetic song with no lawful private source material involved.
    """

    notes = [
        ReviewedBassAuthoringNote(
            source_event_index=0,
            time_seconds=0.0,
            duration_seconds=0.5,
            midi=_BASS_TUNING_MIDI[0],
            string_index=0,
            fret=0,
            techniques=[],
            import_confidence=1.0,
            trust_class=SourceTrustClass.symbolic_verified,
        ),
        ReviewedBassAuthoringNote(
            source_event_index=1,
            time_seconds=1.0,
            duration_seconds=0.5,
            midi=_BASS_TUNING_MIDI[1] + second_note_fret,
            string_index=1,
            fret=second_note_fret,
            techniques=["palm_mute"],
            import_confidence=1.0,
            trust_class=SourceTrustClass.symbolic_verified,
        ),
    ]
    return ReviewedBassAuthoringInput(
        source_track_index=0,
        source_output_json="sources/imported/synthetic-parity-bass.json",
        source_output_sha256="a" * 64,
        recording_sha256="b" * 64,
        score_sha256="c" * 64,
        tuning_midi=_BASS_TUNING_MIDI,
        notes=notes,
    )


def _generator_fixture(*, second_note_fret: int = 2):
    authoring = _synthetic_bass_authoring_input(second_note_fret=second_note_fret)
    reviewed_input = rocksmith_xml_input_from_reviewed_bass(authoring)
    tempo_map = build_deterministic_tempo_map(measure_count=1, bpm=120.0)
    return eof_parity_fixture_from_generator_output(
        fixture_id="synthetic-parity-bass-v1",
        source_kind="synthetic",
        reviewed_input=reviewed_input,
        tempo_map=tempo_map,
    )


def test_generator_output_matches_committed_expected_fixture() -> None:
    expected = _expected_fixture()
    actual = _generator_fixture()

    result = compare_eof_parity_fixtures(expected, actual)

    assert result.matches is True
    assert result.mismatches == ()


def test_generator_regression_is_diagnosed_not_a_trivial_pass() -> None:
    """A real generator defect must actually be caught by this wiring, not just declared clean."""

    expected = _expected_fixture()
    actual = _generator_fixture(second_note_fret=3)

    result = compare_eof_parity_fixtures(expected, actual)

    assert result.matches is False
    assert any(mismatch.field == "notes[1].fret" for mismatch in result.mismatches)
