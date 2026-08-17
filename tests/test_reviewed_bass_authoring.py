from __future__ import annotations

import pytest

from rocksmith_cdlc_generator.reviewed_bass_authoring import bass_authoring_input_from_reviewed_export
from rocksmith_cdlc_generator.reviewed_export_events import ReviewedExportArrangement, ReviewedExportNote
from rocksmith_cdlc_generator.score_source import ArrangementRole
from rocksmith_cdlc_generator.source_import import SourceTrustClass


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


def test_bass_authoring_adapter_rejects_non_bass_arrangement() -> None:
    with pytest.raises(ValueError, match="requires the Bass arrangement"):
        bass_authoring_input_from_reviewed_export(_arrangement(role=ArrangementRole.lead, tuning_midi=(40, 45, 50, 55, 59, 64)))


def test_bass_authoring_adapter_requires_explicit_four_string_tuning() -> None:
    with pytest.raises(ValueError, match="explicit four-string tuning"):
        bass_authoring_input_from_reviewed_export(_arrangement(tuning_midi=None))


@pytest.mark.parametrize(
    ("note", "message"),
    [
        (_note(review_required=True), "still requires human review"),
        (_note(string_index=None, fret=None, position_ready=False), "no confirmed string/fret position"),
        (_note(midi=36), "does not match pitch"),
    ],
)
def test_bass_authoring_adapter_fails_closed_on_unready_source_evidence(note, message) -> None:
    with pytest.raises(ValueError, match=message):
        bass_authoring_input_from_reviewed_export(_arrangement(notes=[note]))
