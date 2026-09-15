from __future__ import annotations

import json
from pathlib import Path

from rocksmith_cdlc_generator.deterministic_tempo_map import (
    TempoChange,
    build_deterministic_tempo_map,
)
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
_TIMING_DRIFT_FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "eof" / "synthetic-parity-timing-drift-v1.json"
)
_TIE_FOLD_FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "eof" / "synthetic-parity-tie-fold-v1.json"
)
_BASS_TUNING_MIDI = (28, 33, 38, 43)
_GUITAR_TUNING_MIDI = (40, 45, 50, 55, 59, 64)


def _expected_fixture(path: Path = _FIXTURE_PATH):
    payload = json.loads(path.read_text())
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


def _synthetic_lead_chord_authoring_input(*, chord_second_fret: int = 0) -> ReviewedGuitarAuthoringInput:
    """Build reviewed Lead authoring input for the fixture's synthetic chord-plus-note song.

    Constructed directly (no project directory, no recording/score files) since the
    fixture is a synthetic song with no lawful private source material involved. The
    first two notes form one explicitly reviewed chord (two simultaneous notes on
    distinct strings); the third note is a separate, non-chord note.
    """

    notes = [
        ReviewedGuitarAuthoringNote(
            source_event_index=0,
            time_seconds=0.0,
            duration_seconds=0.5,
            midi=_GUITAR_TUNING_MIDI[0] + 3,
            string_index=0,
            fret=3,
            techniques=[],
            import_confidence=1.0,
            trust_class=SourceTrustClass.symbolic_verified,
        ),
        ReviewedGuitarAuthoringNote(
            source_event_index=1,
            time_seconds=0.0,
            duration_seconds=0.5,
            midi=_GUITAR_TUNING_MIDI[1] + chord_second_fret,
            string_index=1,
            fret=chord_second_fret,
            techniques=[],
            import_confidence=1.0,
            trust_class=SourceTrustClass.symbolic_verified,
        ),
        ReviewedGuitarAuthoringNote(
            source_event_index=2,
            time_seconds=1.0,
            duration_seconds=0.5,
            midi=_GUITAR_TUNING_MIDI[2] + 2,
            string_index=2,
            fret=2,
            techniques=["palm_mute"],
            import_confidence=1.0,
            trust_class=SourceTrustClass.symbolic_verified,
        ),
    ]
    return ReviewedGuitarAuthoringInput(
        role=ArrangementRole.lead,
        source_track_index=0,
        source_output_json="sources/imported/synthetic-parity-lead-chord.json",
        source_output_sha256="d" * 64,
        recording_sha256="e" * 64,
        score_sha256="f" * 64,
        tuning_midi=_GUITAR_TUNING_MIDI,
        notes=notes,
        chord_groups=[ReviewedGuitarAuthoringChord(source_event_indices=[0, 1])],
    )


def _lead_chord_generator_fixture(*, chord_second_fret: int = 0):
    authoring = _synthetic_lead_chord_authoring_input(chord_second_fret=chord_second_fret)
    reviewed_input = rocksmith_xml_input_from_reviewed_guitar(authoring)
    tempo_map = build_deterministic_tempo_map(measure_count=1, bpm=120.0)
    return eof_parity_fixture_from_generator_output(
        fixture_id="synthetic-parity-lead-chord-v1",
        source_kind="synthetic",
        reviewed_input=reviewed_input,
        tempo_map=tempo_map,
    )


def test_lead_chord_generator_output_matches_committed_expected_fixture() -> None:
    expected = _expected_fixture(_LEAD_CHORD_FIXTURE_PATH)
    actual = _lead_chord_generator_fixture()

    result = compare_eof_parity_fixtures(expected, actual)

    assert result.matches is True
    assert result.mismatches == ()


def test_lead_chord_note_defect_is_diagnosed_not_a_trivial_pass() -> None:
    """A defect in one note of a reviewed chord must be caught, not masked by the chord."""

    expected = _expected_fixture(_LEAD_CHORD_FIXTURE_PATH)
    actual = _lead_chord_generator_fixture(chord_second_fret=2)

    result = compare_eof_parity_fixtures(expected, actual)

    assert result.matches is False
    assert any(mismatch.field == "notes[1].fret" for mismatch in result.mismatches)


def _synthetic_rhythm_chord_authoring_input(*, chord_middle_fret: int = 2) -> ReviewedGuitarAuthoringInput:
    """Build reviewed Rhythm authoring input for the fixture's synthetic three-note-chord song.

    Constructed directly (no project directory, no recording/score files) since the
    fixture is a synthetic song with no lawful private source material involved. The
    first three notes form one explicitly reviewed chord (three simultaneous notes on
    distinct strings, larger than the existing two-note Lead chord fixture); the fourth
    note is a separate, non-chord note.
    """

    notes = [
        ReviewedGuitarAuthoringNote(
            source_event_index=0,
            time_seconds=0.0,
            duration_seconds=0.5,
            midi=_GUITAR_TUNING_MIDI[0] + 2,
            string_index=0,
            fret=2,
            techniques=[],
            import_confidence=1.0,
            trust_class=SourceTrustClass.symbolic_verified,
        ),
        ReviewedGuitarAuthoringNote(
            source_event_index=1,
            time_seconds=0.0,
            duration_seconds=0.5,
            midi=_GUITAR_TUNING_MIDI[1] + chord_middle_fret,
            string_index=1,
            fret=chord_middle_fret,
            techniques=[],
            import_confidence=1.0,
            trust_class=SourceTrustClass.symbolic_verified,
        ),
        ReviewedGuitarAuthoringNote(
            source_event_index=2,
            time_seconds=0.0,
            duration_seconds=0.5,
            midi=_GUITAR_TUNING_MIDI[2] + 0,
            string_index=2,
            fret=0,
            techniques=[],
            import_confidence=1.0,
            trust_class=SourceTrustClass.symbolic_verified,
        ),
        ReviewedGuitarAuthoringNote(
            source_event_index=3,
            time_seconds=1.0,
            duration_seconds=0.5,
            midi=_GUITAR_TUNING_MIDI[3] + 4,
            string_index=3,
            fret=4,
            techniques=["palm_mute"],
            import_confidence=1.0,
            trust_class=SourceTrustClass.symbolic_verified,
        ),
    ]
    return ReviewedGuitarAuthoringInput(
        role=ArrangementRole.rhythm,
        source_track_index=0,
        source_output_json="sources/imported/synthetic-parity-rhythm-chord.json",
        source_output_sha256="1" * 64,
        recording_sha256="2" * 64,
        score_sha256="3" * 64,
        tuning_midi=_GUITAR_TUNING_MIDI,
        notes=notes,
        chord_groups=[ReviewedGuitarAuthoringChord(source_event_indices=[0, 1, 2])],
    )


def _rhythm_chord_generator_fixture(*, chord_middle_fret: int = 2):
    authoring = _synthetic_rhythm_chord_authoring_input(chord_middle_fret=chord_middle_fret)
    reviewed_input = rocksmith_xml_input_from_reviewed_guitar(authoring)
    tempo_map = build_deterministic_tempo_map(measure_count=1, bpm=120.0)
    return eof_parity_fixture_from_generator_output(
        fixture_id="synthetic-parity-rhythm-chord-v1",
        source_kind="synthetic",
        reviewed_input=reviewed_input,
        tempo_map=tempo_map,
    )


def test_rhythm_chord_generator_output_matches_committed_expected_fixture() -> None:
    expected = _expected_fixture(_RHYTHM_CHORD_FIXTURE_PATH)
    actual = _rhythm_chord_generator_fixture()

    result = compare_eof_parity_fixtures(expected, actual)

    assert result.matches is True
    assert result.mismatches == ()


def test_rhythm_chord_middle_note_defect_is_diagnosed_not_a_trivial_pass() -> None:
    """A defect in the middle note of a three-note reviewed chord must still be caught."""

    expected = _expected_fixture(_RHYTHM_CHORD_FIXTURE_PATH)
    actual = _rhythm_chord_generator_fixture(chord_middle_fret=5)

    result = compare_eof_parity_fixtures(expected, actual)

    assert result.matches is False
    assert any(mismatch.field == "notes[1].fret" for mismatch in result.mismatches)


def _synthetic_timing_drift_authoring_input(
    *, second_note_time_seconds: float = 2.0
) -> ReviewedBassAuthoringInput:
    """Build reviewed Bass authoring input for the fixture's synthetic tempo-change song.

    Constructed directly (no project directory, no recording/score files) since the
    fixture is a synthetic song with no lawful private source material involved. The
    first note falls in measure 1 (120 BPM); the second note falls at the measure-2
    tempo-change boundary (90 BPM), so a generator defect that drifts the second
    note's onset off the post-change beat lattice must be caught by comparing
    ``notes[1].onset_seconds`` rather than only the tempo map's own beat lattice.
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
            time_seconds=second_note_time_seconds,
            duration_seconds=0.5,
            midi=_BASS_TUNING_MIDI[1] + 2,
            string_index=1,
            fret=2,
            techniques=["palm_mute"],
            import_confidence=1.0,
            trust_class=SourceTrustClass.symbolic_verified,
        ),
    ]
    return ReviewedBassAuthoringInput(
        source_track_index=0,
        source_output_json="sources/imported/synthetic-parity-timing-drift.json",
        source_output_sha256="7" * 64,
        recording_sha256="8" * 64,
        score_sha256="9" * 64,
        tuning_midi=_BASS_TUNING_MIDI,
        notes=notes,
    )


def _timing_drift_generator_fixture(*, second_note_time_seconds: float = 2.0):
    authoring = _synthetic_timing_drift_authoring_input(
        second_note_time_seconds=second_note_time_seconds
    )
    reviewed_input = rocksmith_xml_input_from_reviewed_bass(authoring)
    tempo_map = build_deterministic_tempo_map(
        measure_count=2, bpm=120.0, tempo_changes=[TempoChange(measure=2, bpm=90.0)]
    )
    return eof_parity_fixture_from_generator_output(
        fixture_id="synthetic-parity-timing-drift-v1",
        source_kind="synthetic",
        reviewed_input=reviewed_input,
        tempo_map=tempo_map,
    )


def test_timing_drift_generator_output_matches_committed_expected_fixture() -> None:
    expected = _expected_fixture(_TIMING_DRIFT_FIXTURE_PATH)
    actual = _timing_drift_generator_fixture()

    result = compare_eof_parity_fixtures(expected, actual)

    assert result.matches is True
    assert result.mismatches == ()


def test_timing_drift_regression_is_diagnosed_not_a_trivial_pass() -> None:
    """A note drifting onto the wrong post-tempo-change beat must still be caught."""

    expected = _expected_fixture(_TIMING_DRIFT_FIXTURE_PATH)
    # One 90 BPM beat (2/3 s) later than the correct post-change onset: the same
    # class of defect as a generator that drifts a note by a whole beat/measure
    # across a tempo change instead of exactly on the changed tempo's lattice.
    actual = _timing_drift_generator_fixture(second_note_time_seconds=2.6666666666666665)

    result = compare_eof_parity_fixtures(expected, actual)

    assert result.matches is False
    assert any(mismatch.field == "notes[1].onset_seconds" for mismatch in result.mismatches)


def _synthetic_lead_tie_fold_authoring_input(
    *, folded_duration_seconds: float = 1.0
) -> ReviewedGuitarAuthoringInput:
    """Build reviewed Lead authoring input for the fixture's synthetic tied-note song.

    Constructed directly (no project directory, no recording/score files) since the
    fixture is a synthetic song with no lawful private source material involved. Note
    0 already reflects an exact tie fold performed upstream (its
    ``continuation_source_event_indices`` names the folded-away continuation note,
    source event 1, and its duration already spans both tied segments); a separate,
    non-tied source event 2 follows. This exercises tie/continuation folding through
    the real generator path (``rocksmith_xml_input_from_reviewed_guitar``) rather than
    only the standalone fold planner.
    """

    notes = [
        ReviewedGuitarAuthoringNote(
            source_event_index=0,
            continuation_source_event_indices=[1],
            time_seconds=0.0,
            duration_seconds=folded_duration_seconds,
            midi=_GUITAR_TUNING_MIDI[0] + 5,
            string_index=0,
            fret=5,
            techniques=[],
            import_confidence=1.0,
            trust_class=SourceTrustClass.symbolic_verified,
        ),
        ReviewedGuitarAuthoringNote(
            source_event_index=2,
            time_seconds=1.0,
            duration_seconds=0.5,
            midi=_GUITAR_TUNING_MIDI[1] + 2,
            string_index=1,
            fret=2,
            techniques=["palm_mute"],
            import_confidence=1.0,
            trust_class=SourceTrustClass.symbolic_verified,
        ),
    ]
    return ReviewedGuitarAuthoringInput(
        role=ArrangementRole.lead,
        source_track_index=0,
        source_output_json="sources/imported/synthetic-parity-tie-fold.json",
        source_output_sha256="4" * 64,
        recording_sha256="5" * 64,
        score_sha256="6" * 64,
        tuning_midi=_GUITAR_TUNING_MIDI,
        notes=notes,
    )


def _lead_tie_fold_generator_fixture(*, folded_duration_seconds: float = 1.0):
    authoring = _synthetic_lead_tie_fold_authoring_input(
        folded_duration_seconds=folded_duration_seconds
    )
    reviewed_input = rocksmith_xml_input_from_reviewed_guitar(authoring)
    tempo_map = build_deterministic_tempo_map(measure_count=1, bpm=120.0)
    return eof_parity_fixture_from_generator_output(
        fixture_id="synthetic-parity-tie-fold-v1",
        source_kind="synthetic",
        reviewed_input=reviewed_input,
        tempo_map=tempo_map,
    )


def test_tie_fold_generator_output_matches_committed_expected_fixture() -> None:
    expected = _expected_fixture(_TIE_FOLD_FIXTURE_PATH)
    actual = _lead_tie_fold_generator_fixture()

    result = compare_eof_parity_fixtures(expected, actual)

    assert result.matches is True
    assert result.mismatches == ()


def test_tie_fold_regression_is_diagnosed_not_a_trivial_pass() -> None:
    """A fold that fails to extend duration across the tied continuation must be caught."""

    expected = _expected_fixture(_TIE_FOLD_FIXTURE_PATH)
    # Reverts to the un-folded first segment's duration, as if the continuation's
    # note head were never folded into note 0 at all.
    actual = _lead_tie_fold_generator_fixture(folded_duration_seconds=0.5)

    result = compare_eof_parity_fixtures(expected, actual)

    assert result.matches is False
    assert any(mismatch.field == "notes[0].duration_seconds" for mismatch in result.mismatches)
