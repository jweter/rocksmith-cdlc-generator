from __future__ import annotations

import pytest

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
from rocksmith_cdlc_generator.source_import import SourceBendPoint, SourceTrustClass

_SHA_A = "a" * 64
_SHA_B = "b" * 64
_SHA_C = "c" * 64


def _bass_note(
    *,
    techniques: list[str] | None = None,
    bend_points: list[SourceBendPoint] | None = None,
    slide_target_fret: int | None = None,
    link_next: bool = False,
) -> ReviewedBassAuthoringNote:
    return ReviewedBassAuthoringNote(
        source_event_index=7,
        continuation_source_event_indices=[8, 9],
        time_seconds=1.25,
        duration_seconds=0.5,
        midi=40,
        string_index=0,
        fret=12,
        techniques=techniques or ["palm_mute"],
        bend_points=bend_points or [],
        slide_target_fret=slide_target_fret,
        link_next=link_next,
        import_confidence=0.94,
        trust_class=SourceTrustClass.symbolic_verified,
    )


def _bass_input(
    *,
    techniques: list[str] | None = None,
    bend_points: list[SourceBendPoint] | None = None,
    slide_target_fret: int | None = None,
    link_next: bool = False,
) -> ReviewedBassAuthoringInput:
    return ReviewedBassAuthoringInput(
        source_track_index=2,
        source_output_json="sources/imported/bass.json",
        source_output_sha256=_SHA_A,
        recording_sha256=_SHA_B,
        score_sha256=_SHA_C,
        tuning_midi=(28, 33, 38, 43),
        notes=[
            _bass_note(
                techniques=techniques,
                bend_points=bend_points,
                slide_target_fret=slide_target_fret,
                link_next=link_next,
            )
        ],
        human_confirmed_timing=True,
    )


def _guitar_note(
    index: int,
    *,
    time_seconds: float,
    midi: int,
    string_index: int,
    fret: int,
) -> ReviewedGuitarAuthoringNote:
    return ReviewedGuitarAuthoringNote(
        source_event_index=index,
        time_seconds=time_seconds,
        duration_seconds=0.6,
        midi=midi,
        string_index=string_index,
        fret=fret,
        techniques=[],
        import_confidence=0.96,
        trust_class=SourceTrustClass.user_confirmed,
    )


def _guitar_input() -> ReviewedGuitarAuthoringInput:
    notes = [
        _guitar_note(0, time_seconds=2.0, midi=40, string_index=0, fret=0),
        _guitar_note(1, time_seconds=2.0, midi=45, string_index=1, fret=0),
        _guitar_note(2, time_seconds=3.0, midi=52, string_index=2, fret=2),
    ]
    return ReviewedGuitarAuthoringInput(
        role=ArrangementRole.lead,
        source_track_index=4,
        source_output_json="sources/imported/lead.json",
        source_output_sha256=_SHA_A,
        recording_sha256=_SHA_B,
        score_sha256=_SHA_C,
        tuning_midi=(40, 45, 50, 55, 59, 64),
        notes=notes,
        chord_groups=[ReviewedGuitarAuthoringChord(source_event_indices=[0, 1])],
        human_confirmed_timing=True,
    )


def test_bass_handoff_preserves_reviewed_timing_position_and_provenance() -> None:
    result = rocksmith_xml_input_from_reviewed_bass(_bass_input())

    assert result.role is ArrangementRole.bass
    assert result.human_confirmed_timing is True
    assert result.score_sha256 == _SHA_C
    assert result.recording_sha256 == _SHA_B
    assert result.tuning_midi == (28, 33, 38, 43)
    assert result.chords == []
    assert result.notes[0].source_event_index == 7
    assert result.notes[0].continuation_source_event_indices == [8, 9]
    assert result.notes[0].time_seconds == pytest.approx(1.25)
    assert result.notes[0].string_index == 0
    assert result.notes[0].fret == 12
    assert result.notes[0].techniques == ["palm_mute"]


def test_guitar_handoff_preserves_reviewed_chord_membership_and_shape() -> None:
    result = rocksmith_xml_input_from_reviewed_guitar(_guitar_input())

    assert result.role is ArrangementRole.lead
    assert [note.source_event_index for note in result.notes] == [0, 1, 2]
    assert len(result.chords) == 1
    chord = result.chords[0]
    assert chord.source_event_indices == [0, 1]
    assert [note.source_event_index for note in chord.notes] == [0, 1]
    assert chord.time_seconds == pytest.approx(2.0)
    assert chord.sustain_seconds == pytest.approx(0.6)
    assert chord.shape == (0, 0, -1, -1, -1, -1)


def test_handoff_fails_closed_on_unsupported_technique_semantics() -> None:
    with pytest.raises(ValueError, match="not losslessly supported yet: grace"):
        rocksmith_xml_input_from_reviewed_bass(_bass_input(techniques=["grace"]))


def test_handoff_allows_hammer_on_and_pull_off_through() -> None:
    hammer_note = rocksmith_xml_input_from_reviewed_bass(
        _bass_input(techniques=["hammer_on"])
    ).notes[0]
    pull_note = rocksmith_xml_input_from_reviewed_bass(
        _bass_input(techniques=["pull_off"])
    ).notes[0]
    assert hammer_note.techniques == ["hammer_on"]
    assert pull_note.techniques == ["pull_off"]


def test_handoff_fails_closed_on_bend_without_curve_data() -> None:
    with pytest.raises(ValueError, match="not losslessly supported yet: bend"):
        rocksmith_xml_input_from_reviewed_bass(_bass_input(techniques=["bend"]))


def test_handoff_allows_bend_with_curve_data_through_and_preserves_it() -> None:
    points = [
        SourceBendPoint(position=0.0, semitones=0.0),
        SourceBendPoint(position=1.0, semitones=1.0),
    ]
    result = rocksmith_xml_input_from_reviewed_bass(
        _bass_input(techniques=["bend"], bend_points=points)
    )

    assert result.notes[0].techniques == ["bend"]
    assert result.notes[0].bend_points == points


def test_handoff_fails_closed_on_slide_without_resolved_target() -> None:
    with pytest.raises(ValueError, match="not losslessly supported yet: slide"):
        rocksmith_xml_input_from_reviewed_bass(_bass_input(techniques=["slide"]))


def test_handoff_allows_slide_with_resolved_target_through_and_preserves_it() -> None:
    result = rocksmith_xml_input_from_reviewed_bass(
        _bass_input(techniques=["slide"], slide_target_fret=7, link_next=True)
    )

    assert result.notes[0].techniques == ["slide"]
    assert result.notes[0].slide_target_fret == 7
    assert result.notes[0].link_next is True
