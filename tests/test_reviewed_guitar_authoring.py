from __future__ import annotations

import pytest

from rocksmith_cdlc_generator.reviewed_export_events import (
    ReviewedExportArrangement,
    ReviewedExportChordGroup,
    ReviewedExportNote,
)
from rocksmith_cdlc_generator.reviewed_guitar_authoring import (
    guitar_authoring_input_from_reviewed_export,
)
from rocksmith_cdlc_generator.score_source import ArrangementRole
from rocksmith_cdlc_generator.source_import import SourceTrustClass

_SHA_A = "a" * 64
_SHA_B = "b" * 64
_SHA_C = "c" * 64
_TUNING = (40, 45, 50, 55, 59, 64)


def _note(
    index: int,
    *,
    time_seconds: float,
    midi: int,
    string_index: int | None,
    fret: int | None,
    trust: SourceTrustClass = SourceTrustClass.symbolic_verified,
    review_required: bool = False,
    source_duration_seconds: float = 0.5,
    reviewed_start_seconds: float | None = None,
    reviewed_duration_seconds: float = 0.55,
    techniques: list[str] | None = None,
) -> ReviewedExportNote:
    return ReviewedExportNote(
        source_event_index=index,
        source_start_seconds=time_seconds,
        source_duration_seconds=source_duration_seconds,
        reviewed_start_seconds=(time_seconds + 1.0 if reviewed_start_seconds is None else reviewed_start_seconds),
        reviewed_duration_seconds=reviewed_duration_seconds,
        midi=midi,
        note_name=None,
        string_index=string_index,
        fret=fret,
        techniques=((["hammer_on"] if index == 0 else []) if techniques is None else techniques),
        import_confidence=0.9,
        trust_class=trust,
        review_required=review_required,
        position_ready=string_index is not None and fret is not None,
    )


def _arrangement(
    role: ArrangementRole = ArrangementRole.lead,
) -> ReviewedExportArrangement:
    return ReviewedExportArrangement(
        role=role,
        source_track_index=4,
        source_output_json=f"sources/imported/{role.value}.json",
        source_output_sha256=_SHA_A,
        recording_sha256=_SHA_B,
        score_sha256=_SHA_C,
        tuning_midi=_TUNING,
        notes=[
            _note(0, time_seconds=0.0, midi=40, string_index=0, fret=0),
            _note(1, time_seconds=0.0, midi=45, string_index=1, fret=0),
            _note(2, time_seconds=1.0, midi=52, string_index=2, fret=2),
        ],
        chord_groups=[ReviewedExportChordGroup(source_event_indices=[0, 1])],
        human_confirmed_timing=True,
    )


@pytest.mark.parametrize("role", [ArrangementRole.lead, ArrangementRole.rhythm])
def test_guitar_adapter_preserves_reviewed_timing_positions_and_chords(role) -> None:
    result = guitar_authoring_input_from_reviewed_export(_arrangement(role))

    assert result.role is role
    assert result.tuning_midi == _TUNING
    assert result.human_confirmed_timing is True
    assert [note.source_event_index for note in result.notes] == [0, 1, 2]
    assert result.notes[0].time_seconds == pytest.approx(1.0)
    assert result.notes[0].duration_seconds == pytest.approx(0.55)
    assert result.notes[0].techniques == ["hammer_on"]
    assert [group.source_event_indices for group in result.chord_groups] == [[0, 1]]


@pytest.mark.parametrize("role", [ArrangementRole.lead, ArrangementRole.rhythm])
def test_guitar_adapter_folds_exact_tied_chord_without_inventing_identity(role) -> None:
    notes = [
        _note(
            0,
            time_seconds=0.0,
            midi=40,
            string_index=0,
            fret=0,
            reviewed_duration_seconds=0.5,
            techniques=[],
        ),
        _note(
            1,
            time_seconds=0.0,
            midi=45,
            string_index=1,
            fret=0,
            reviewed_duration_seconds=0.5,
            techniques=[],
        ),
        _note(
            2,
            time_seconds=0.5,
            midi=40,
            string_index=0,
            fret=0,
            reviewed_start_seconds=1.5,
            reviewed_duration_seconds=0.5,
            techniques=["tie"],
            review_required=True,
        ),
        _note(
            3,
            time_seconds=0.5,
            midi=45,
            string_index=1,
            fret=0,
            reviewed_start_seconds=1.5,
            reviewed_duration_seconds=0.5,
            techniques=["tie"],
            review_required=True,
        ),
    ]
    arrangement = ReviewedExportArrangement(
        role=role,
        source_track_index=4,
        source_output_json=f"sources/imported/{role.value}.json",
        source_output_sha256=_SHA_A,
        recording_sha256=_SHA_B,
        score_sha256=_SHA_C,
        tuning_midi=_TUNING,
        notes=notes,
        chord_groups=[
            ReviewedExportChordGroup(source_event_indices=[0, 1]),
            ReviewedExportChordGroup(source_event_indices=[2, 3]),
        ],
        human_confirmed_timing=True,
    )

    result = guitar_authoring_input_from_reviewed_export(arrangement)

    assert [note.source_event_index for note in result.notes] == [0, 1]
    assert [note.continuation_source_event_indices for note in result.notes] == [
        [2],
        [3],
    ]
    assert [note.duration_seconds for note in result.notes] == pytest.approx([1.0, 1.0])
    assert [group.source_event_indices for group in result.chord_groups] == [[0, 1]]


def test_guitar_adapter_rejects_mixed_tie_chord_without_reviewed_primary_identity() -> None:
    notes = [
        _note(
            0,
            time_seconds=0.0,
            midi=40,
            string_index=0,
            fret=0,
            reviewed_duration_seconds=0.5,
            techniques=[],
        ),
        _note(
            1,
            time_seconds=0.5,
            midi=40,
            string_index=0,
            fret=0,
            reviewed_start_seconds=1.5,
            reviewed_duration_seconds=0.5,
            techniques=["tie"],
            review_required=True,
        ),
        _note(
            2,
            time_seconds=0.5,
            midi=47,
            string_index=1,
            fret=2,
            reviewed_start_seconds=1.5,
            reviewed_duration_seconds=0.5,
            techniques=[],
        ),
    ]
    arrangement = ReviewedExportArrangement(
        role=ArrangementRole.lead,
        source_track_index=4,
        source_output_json="sources/imported/lead.json",
        source_output_sha256=_SHA_A,
        recording_sha256=_SHA_B,
        score_sha256=_SHA_C,
        tuning_midi=_TUNING,
        notes=notes,
        chord_groups=[ReviewedExportChordGroup(source_event_indices=[1, 2])],
        human_confirmed_timing=True,
    )

    with pytest.raises(ValueError, match="alter reviewed guitar chord identity"):
        guitar_authoring_input_from_reviewed_export(arrangement)


def test_guitar_adapter_rejects_bass() -> None:
    arrangement = _arrangement(ArrangementRole.lead).model_copy(
        update={"role": ArrangementRole.bass, "chord_groups": []}
    )
    with pytest.raises(ValueError, match="Lead or Rhythm"):
        guitar_authoring_input_from_reviewed_export(arrangement)


def test_guitar_adapter_rejects_note_still_requiring_review() -> None:
    arrangement = _arrangement().model_copy(
        update={
            "notes": [
                _note(
                    0,
                    time_seconds=0.0,
                    midi=40,
                    string_index=0,
                    fret=0,
                    review_required=True,
                )
            ]
        }
    )
    with pytest.raises(ValueError, match="still requires human review"):
        guitar_authoring_input_from_reviewed_export(arrangement)


def test_guitar_adapter_rejects_unaccepted_source_trust() -> None:
    arrangement = _arrangement().model_copy(
        update={
            "notes": [
                _note(
                    0,
                    time_seconds=0.0,
                    midi=40,
                    string_index=0,
                    fret=0,
                    trust=SourceTrustClass.symbolic_unverified,
                )
            ],
            "chord_groups": [],
        }
    )
    with pytest.raises(ValueError, match="accepted source trust"):
        guitar_authoring_input_from_reviewed_export(arrangement)


def test_guitar_adapter_rejects_missing_position() -> None:
    arrangement = _arrangement().model_copy(
        update={
            "notes": [_note(0, time_seconds=0.0, midi=40, string_index=None, fret=None)],
            "chord_groups": [],
        }
    )
    with pytest.raises(ValueError, match="no confirmed string/fret position"):
        guitar_authoring_input_from_reviewed_export(arrangement)


def test_guitar_adapter_rejects_pitch_inconsistent_position() -> None:
    arrangement = _arrangement().model_copy(
        update={
            "notes": [_note(0, time_seconds=0.0, midi=41, string_index=0, fret=0)],
            "chord_groups": [],
        }
    )
    with pytest.raises(ValueError, match="does not match pitch"):
        guitar_authoring_input_from_reviewed_export(arrangement)


def test_guitar_adapter_requires_explicit_six_string_tuning() -> None:
    arrangement = _arrangement().model_copy(update={"tuning_midi": (40, 45, 50, 55)})
    with pytest.raises(ValueError, match="six-string tuning"):
        guitar_authoring_input_from_reviewed_export(arrangement)
