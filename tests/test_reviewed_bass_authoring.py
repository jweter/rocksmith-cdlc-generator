from __future__ import annotations

import pytest

from rocksmith_cdlc_generator.reviewed_bass_authoring import (
    bass_authoring_input_from_reviewed_export,
)
from rocksmith_cdlc_generator.reviewed_export_events import (
    ReviewedExportArrangement,
    ReviewedExportNote,
)
from rocksmith_cdlc_generator.score_source import ArrangementRole
from rocksmith_cdlc_generator.source_import import SourceBendPoint, SourceTrustClass

_SHA_A = "a" * 64
_SHA_B = "b" * 64
_SHA_C = "c" * 64


def _note(**updates) -> ReviewedExportNote:
    values = dict(
        source_event_index=3,
        source_start_seconds=1.0,
        source_duration_seconds=0.5,
        reviewed_start_seconds=2.2,
        reviewed_duration_seconds=0.4,
        midi=35,
        string_index=0,
        fret=7,
        techniques=["palm_mute"],
        import_confidence=0.98,
        trust_class=SourceTrustClass.symbolic_verified,
        review_required=False,
        position_ready=True,
    )
    values.update(updates)
    return ReviewedExportNote(**values)


def _arrangement(**updates) -> ReviewedExportArrangement:
    values = dict(
        role=ArrangementRole.bass,
        source_track_index=2,
        source_output_json="sources/imported/bass.json",
        source_output_sha256=_SHA_A,
        recording_sha256=_SHA_B,
        score_sha256=_SHA_C,
        tuning_midi=(28, 33, 38, 43),
        notes=[_note()],
        human_confirmed_timing=True,
    )
    values.update(updates)
    return ReviewedExportArrangement(**values)


def test_bass_authoring_adapter_preserves_reviewed_timing_position_and_provenance() -> None:
    adapted = bass_authoring_input_from_reviewed_export(_arrangement())

    assert adapted.source_track_index == 2
    assert adapted.source_output_sha256 == _SHA_A
    assert adapted.recording_sha256 == _SHA_B
    assert adapted.score_sha256 == _SHA_C
    assert adapted.tuning_midi == (28, 33, 38, 43)
    assert adapted.human_confirmed_timing is True
    assert len(adapted.notes) == 1
    note = adapted.notes[0]
    assert note.source_event_index == 3
    assert note.time_seconds == pytest.approx(2.2)
    assert note.duration_seconds == pytest.approx(0.4)
    assert note.string_index == 0
    assert note.fret == 7
    assert note.techniques == ["palm_mute"]
    assert note.import_confidence == pytest.approx(0.98)
    assert note.trust_class is SourceTrustClass.symbolic_verified


def test_bass_authoring_adapter_folds_exact_tie_chain_with_lineage() -> None:
    notes = [
        _note(
            source_event_index=3,
            source_start_seconds=1.0,
            source_duration_seconds=0.5,
            reviewed_start_seconds=2.2,
            reviewed_duration_seconds=0.4,
            techniques=[],
            composition_source_track_index=2,
            composition_source_event_index=3,
        ),
        _note(
            source_event_index=4,
            source_start_seconds=1.5,
            source_duration_seconds=0.5,
            reviewed_start_seconds=2.6,
            reviewed_duration_seconds=0.45,
            techniques=["tie"],
            review_required=True,
            composition_source_track_index=2,
            composition_source_event_index=4,
        ),
        _note(
            source_event_index=5,
            source_start_seconds=2.0,
            source_duration_seconds=0.25,
            reviewed_start_seconds=3.05,
            reviewed_duration_seconds=0.2,
            techniques=["tie"],
            review_required=True,
            composition_source_track_index=2,
            composition_source_event_index=5,
        ),
    ]

    adapted = bass_authoring_input_from_reviewed_export(_arrangement(notes=notes))

    assert len(adapted.notes) == 1
    assert adapted.notes[0].source_event_index == 3
    assert adapted.notes[0].continuation_source_event_indices == [4, 5]
    assert adapted.notes[0].duration_seconds == pytest.approx(1.05)
    assert adapted.notes[0].techniques == []


def test_bass_authoring_adapter_does_not_fold_a_tie_across_composed_tracks() -> None:
    notes = [
        _note(
            source_event_index=3,
            source_start_seconds=1.0,
            source_duration_seconds=0.5,
            reviewed_start_seconds=2.0,
            reviewed_duration_seconds=0.5,
            techniques=[],
            composition_source_track_index=2,
            composition_source_event_index=7,
        ),
        _note(
            source_event_index=4,
            source_start_seconds=1.5,
            reviewed_start_seconds=2.5,
            reviewed_duration_seconds=0.5,
            techniques=["tie"],
            review_required=True,
            composition_source_track_index=3,
            composition_source_event_index=11,
        ),
    ]

    with pytest.raises(ValueError, match="still requires human review"):
        bass_authoring_input_from_reviewed_export(_arrangement(notes=notes))


def test_bass_authoring_adapter_does_not_bridge_a_tie_across_a_gap() -> None:
    notes = [
        _note(
            source_event_index=3,
            source_start_seconds=1.0,
            source_duration_seconds=0.4,
            reviewed_start_seconds=2.0,
            reviewed_duration_seconds=0.4,
            techniques=[],
        ),
        _note(
            source_event_index=4,
            source_start_seconds=1.5,
            reviewed_start_seconds=2.5,
            techniques=["tie"],
            review_required=True,
        ),
    ]

    with pytest.raises(ValueError, match="still requires human review"):
        bass_authoring_input_from_reviewed_export(_arrangement(notes=notes))


def test_bass_authoring_adapter_validates_folded_tie_trust() -> None:
    notes = [
        _note(
            source_event_index=3,
            source_start_seconds=1.0,
            source_duration_seconds=0.5,
            reviewed_start_seconds=2.0,
            reviewed_duration_seconds=0.5,
            techniques=[],
        ),
        _note(
            source_event_index=4,
            source_start_seconds=1.5,
            reviewed_start_seconds=2.5,
            techniques=["tie"],
            review_required=True,
            trust_class=SourceTrustClass.symbolic_unverified,
        ),
    ]

    with pytest.raises(ValueError, match="accepted source trust"):
        bass_authoring_input_from_reviewed_export(_arrangement(notes=notes))


def test_bass_authoring_adapter_preserves_bend_curve() -> None:
    points = [
        SourceBendPoint(position=0.0, semitones=0.0),
        SourceBendPoint(position=1.0, semitones=2.0),
    ]
    adapted = bass_authoring_input_from_reviewed_export(
        _arrangement(notes=[_note(techniques=["bend"], bend_points=points)])
    )

    assert adapted.notes[0].bend_points == points


def test_bass_authoring_adapter_rejects_non_bass_arrangement() -> None:
    with pytest.raises(ValueError, match="requires the Bass arrangement"):
        bass_authoring_input_from_reviewed_export(
            _arrangement(role=ArrangementRole.lead, tuning_midi=(40, 45, 50, 55, 59, 64))
        )


def test_bass_authoring_adapter_requires_explicit_four_string_tuning() -> None:
    with pytest.raises(ValueError, match="explicit four-string tuning"):
        bass_authoring_input_from_reviewed_export(_arrangement(tuning_midi=None))


@pytest.mark.parametrize(
    ("note", "message"),
    [
        (_note(review_required=True), "still requires human review"),
        (
            _note(trust_class=SourceTrustClass.symbolic_unverified),
            "does not have accepted source trust",
        ),
        (
            _note(string_index=None, fret=None, position_ready=False),
            "no confirmed string/fret position",
        ),
        (_note(midi=36), "does not match pitch"),
    ],
)
def test_bass_authoring_adapter_fails_closed_on_unready_source_evidence(note, message) -> None:
    with pytest.raises(ValueError, match=message):
        bass_authoring_input_from_reviewed_export(_arrangement(notes=[note]))
