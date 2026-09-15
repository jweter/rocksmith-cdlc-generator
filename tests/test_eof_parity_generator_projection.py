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
from rocksmith_cdlc_generator.reviewed_guitar_authoring import (
    ReviewedGuitarAuthoringChord,
    ReviewedGuitarAuthoringInput,
    ReviewedGuitarAuthoringNote,
)
from rocksmith_cdlc_generator.reviewed_rocksmith_xml import (
    rocksmith_xml_input_from_reviewed_bass,
    rocksmith_xml_input_from_reviewed_guitar,
)
from rocksmith_cdlc_generator.score_source import ArrangementRole
from rocksmith_cdlc_generator.source_import import SourceTrustClass

_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "eof" / "synthetic-parity-bass-v1.json"
_LEAD_CHORD_FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "eof" / "synthetic-parity-lead-chord-v1.json"
)
_RHYTHM_CHORD_FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "eof" / "synthetic-parity-rhythm-chord-v1.json"
)
_BASS_TUNING_MIDI = (28, 33, 38, 43)
_GUITAR_TUNING_MIDI = (40, 45, 50, 55, 59, 64)


def _expected_fixture(path: Path = _FIXTURE_PATH):
    payload = json.loads(path.read_text())
    return parse_eof_parity_fixture(payload)


def _synthetic_bass_authoring_input(*, second_note_fret: int = 2) -> ReviewedBassAuthoringInput:
    notes = [
        ReviewedBassAuthoringNote(source_event_index=0, time_seconds=0.0, duration_seconds=0.5, midi=_BASS_TUNING_MIDI[0], string_index=0, fret=0, techniques=[], import_confidence=1.0, trust_class=SourceTrustClass.symbolic_verified),
        ReviewedBassAuthoringNote(source_event_index=1, time_seconds=1.0, duration_seconds=0.5, midi=_BASS_TUNING_MIDI[1] + second_note_fret, string_index=1, fret=second_note_fret, techniques=["palm_mute"], import_confidence=1.0, trust_class=SourceTrustClass.symbolic_verified),
    ]
    return ReviewedBassAuthoringInput(source_track_index=0, source_output_json="sources/imported/synthetic-parity-bass.json", source_output_sha256="a" * 64, recording_sha256="b" * 64, score_sha256="c" * 64, tuning_midi=_BASS_TUNING_MIDI, notes=notes)


def _generator_fixture(*, second_note_fret: int = 2):
    reviewed_input = rocksmith_xml_input_from_reviewed_bass(_synthetic_bass_authoring_input(second_note_fret=second_note_fret))
    return eof_parity_fixture_from_generator_output(fixture_id="synthetic-parity-bass-v1", source_kind="synthetic", reviewed_input=reviewed_input, tempo_map=build_deterministic_tempo_map(measure_count=1, bpm=120.0))


def test_generator_output_matches_committed_expected_fixture() -> None:
    result = compare_eof_parity_fixtures(_expected_fixture(), _generator_fixture())
    assert result.matches is True
    assert result.mismatches == ()


def test_generator_regression_is_diagnosed_not_a_trivial_pass() -> None:
    result = compare_eof_parity_fixtures(_expected_fixture(), _generator_fixture(second_note_fret=3))
    assert result.matches is False
    assert any(mismatch.field == "notes[1].fret" for mismatch in result.mismatches)


def _synthetic_guitar_chord_authoring_input(*, role: ArrangementRole, chord_second_fret: int = 0) -> ReviewedGuitarAuthoringInput:
    notes = [
        ReviewedGuitarAuthoringNote(source_event_index=0, time_seconds=0.0, duration_seconds=0.5, midi=_GUITAR_TUNING_MIDI[0] + 3, string_index=0, fret=3, techniques=[], import_confidence=1.0, trust_class=SourceTrustClass.symbolic_verified),
        ReviewedGuitarAuthoringNote(source_event_index=1, time_seconds=0.0, duration_seconds=0.5, midi=_GUITAR_TUNING_MIDI[1] + chord_second_fret, string_index=1, fret=chord_second_fret, techniques=[], import_confidence=1.0, trust_class=SourceTrustClass.symbolic_verified),
        ReviewedGuitarAuthoringNote(source_event_index=2, time_seconds=1.0, duration_seconds=0.5, midi=_GUITAR_TUNING_MIDI[2] + 2, string_index=2, fret=2, techniques=["palm_mute"], import_confidence=1.0, trust_class=SourceTrustClass.symbolic_verified),
    ]
    return ReviewedGuitarAuthoringInput(role=role, source_track_index=0, source_output_json=f"sources/imported/synthetic-parity-{role.value}-chord.json", source_output_sha256="d" * 64, recording_sha256="e" * 64, score_sha256="f" * 64, tuning_midi=_GUITAR_TUNING_MIDI, notes=notes, chord_groups=[ReviewedGuitarAuthoringChord(source_event_indices=[0, 1])])


def _guitar_chord_generator_fixture(*, role: ArrangementRole, fixture_id: str, chord_second_fret: int = 0):
    reviewed_input = rocksmith_xml_input_from_reviewed_guitar(_synthetic_guitar_chord_authoring_input(role=role, chord_second_fret=chord_second_fret))
    return eof_parity_fixture_from_generator_output(fixture_id=fixture_id, source_kind="synthetic", reviewed_input=reviewed_input, tempo_map=build_deterministic_tempo_map(measure_count=1, bpm=120.0))


def test_lead_chord_generator_output_matches_committed_expected_fixture() -> None:
    actual = _guitar_chord_generator_fixture(role=ArrangementRole.lead, fixture_id="synthetic-parity-lead-chord-v1")
    result = compare_eof_parity_fixtures(_expected_fixture(_LEAD_CHORD_FIXTURE_PATH), actual)
    assert result.matches is True
    assert result.mismatches == ()


def test_lead_chord_note_defect_is_diagnosed_not_a_trivial_pass() -> None:
    actual = _guitar_chord_generator_fixture(role=ArrangementRole.lead, fixture_id="synthetic-parity-lead-chord-v1", chord_second_fret=2)
    result = compare_eof_parity_fixtures(_expected_fixture(_LEAD_CHORD_FIXTURE_PATH), actual)
    assert result.matches is False
    assert any(mismatch.field == "notes[1].fret" for mismatch in result.mismatches)


def test_rhythm_chord_generator_output_matches_committed_expected_fixture() -> None:
    actual = _guitar_chord_generator_fixture(role=ArrangementRole.rhythm, fixture_id="synthetic-parity-rhythm-chord-v1")
    result = compare_eof_parity_fixtures(_expected_fixture(_RHYTHM_CHORD_FIXTURE_PATH), actual)
    assert result.matches is True
    assert result.mismatches == ()


def test_rhythm_chord_note_defect_is_diagnosed_not_a_trivial_pass() -> None:
    actual = _guitar_chord_generator_fixture(role=ArrangementRole.rhythm, fixture_id="synthetic-parity-rhythm-chord-v1", chord_second_fret=2)
    result = compare_eof_parity_fixtures(_expected_fixture(_RHYTHM_CHORD_FIXTURE_PATH), actual)
    assert result.matches is False
    assert any(mismatch.field == "notes[1].fret" for mismatch in result.mismatches)
