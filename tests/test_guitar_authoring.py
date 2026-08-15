from __future__ import annotations

from pathlib import Path

import pytest

from rocksmith_cdlc_generator.alignment import AlignmentAnchor, AlignmentReport
from rocksmith_cdlc_generator.guitar_authoring import build_guitar_authoring_chart
from rocksmith_cdlc_generator.source_import import (
    ImportedSource,
    SourceNoteEvent,
    SourceProvenance,
    SourceTrack,
    SourceTrustClass,
)


def _alignment(sha: str, track_index: int = 2, confidence: float = 0.9) -> AlignmentReport:
    return AlignmentReport(
        source_path="fixture.gp5",
        source_sha256=sha,
        track_index=track_index,
        audio_beat_start_index=0,
        global_offset_seconds=1.0,
        anchor_stride_beats=8,
        matched_beats=8,
        rms_residual_seconds=0.01,
        median_abs_residual_seconds=0.01,
        max_abs_residual_seconds=0.02,
        confidence=confidence,
        anchors=[
            AlignmentAnchor(source_time_seconds=0.0, audio_time_seconds=1.0, source_beat_index=0, audio_beat_index=0, confidence=0.9),
            AlignmentAnchor(source_time_seconds=4.0, audio_time_seconds=5.0, source_beat_index=8, audio_beat_index=8, confidence=0.9),
        ],
        regions=[],
    )


def _source(notes: list[SourceNoteEvent], *, sha: str = "a" * 64, instrument: str = "lead") -> ImportedSource:
    return ImportedSource(
        provenance=SourceProvenance(
            source_type="gp5",
            source_filename="fixture.gp5",
            source_sha256=sha,
            importer="test",
            importer_version="1",
        ),
        tracks=[
            SourceTrack(
                source_track_index=2,
                name="Lead Guitar",
                instrument=instrument,
                tuning_midi=[40, 45, 50, 55, 59, 64],
                notes=notes,
            )
        ],
    )


def _note(start: float, string: int | None, fret: int | None, midi: int, *, verified: bool = True) -> SourceNoteEvent:
    return SourceNoteEvent(
        start_seconds=start,
        duration_seconds=0.5,
        midi=midi,
        string_index=string,
        fret=fret,
        techniques=["palm_mute"] if string == 0 else [],
        trust_class=SourceTrustClass.symbolic_verified if verified else SourceTrustClass.symbolic_unverified,
        import_confidence=1.0,
        review_required=False,
    )


def test_groups_simultaneous_six_string_notes_into_chord() -> None:
    source = _source([
        _note(0.5, 0, 3, 43),
        _note(0.5, 1, 5, 50),
        _note(0.5, 2, 5, 55),
        _note(1.5, 3, 0, 55),
    ])
    chart = build_guitar_authoring_chart(source, _alignment("a" * 64), arrangement="lead")

    assert len(chart.chords) == 1
    assert chart.chords[0].shape == (3, 5, 5, -1, -1, -1)
    assert [note.string_index for note in chart.chords[0].notes] == [0, 1, 2]
    assert chart.chords[0].start_seconds == pytest.approx(1.5)
    assert len(chart.single_notes) == 1
    assert chart.single_notes[0].start_seconds == pytest.approx(2.5)
    assert chart.unresolved_notes == []


def test_reviewed_group_overrides_automatic_onset_grouping() -> None:
    source = _source([
        _note(0.50, 0, 3, 43),
        _note(0.54, 1, 5, 50),
        _note(1.50, 3, 0, 55),
    ])
    automatic = build_guitar_authoring_chart(
        source, _alignment("a" * 64), arrangement="lead"
    )
    assert automatic.chords == []
    assert len(automatic.single_notes) == 3

    reviewed = build_guitar_authoring_chart(
        source,
        _alignment("a" * 64),
        arrangement="lead",
        reviewed_chord_groups=[[0, 1]],
    )
    assert len(reviewed.chords) == 1
    assert reviewed.chords[0].shape == (3, 5, -1, -1, -1, -1)
    assert [note.midi for note in reviewed.chords[0].notes] == [43, 50]
    assert [note.midi for note in reviewed.single_notes] == [55]


def test_reviewed_group_does_not_export_partial_chord_when_member_is_unresolved() -> None:
    source = _source([
        _note(0.50, 0, 3, 43),
        _note(0.54, None, None, 50),
    ])
    chart = build_guitar_authoring_chart(
        source,
        _alignment("a" * 64),
        arrangement="lead",
        reviewed_chord_groups=[[0, 1]],
    )
    assert chart.chords == []
    assert chart.single_notes == []
    assert {item.reason for item in chart.unresolved_notes} == {
        "string_fret_unresolved",
        "reviewed_chord_incomplete",
    }


def test_reuses_deterministic_chord_id_for_same_shape() -> None:
    source = _source([
        _note(0.0, 0, 3, 43), _note(0.0, 1, 5, 50),
        _note(1.0, 0, 3, 43), _note(1.0, 1, 5, 50),
        _note(2.0, 0, 5, 45), _note(2.0, 1, 7, 52),
    ])
    chart = build_guitar_authoring_chart(source, _alignment("a" * 64), arrangement="lead")

    assert [chord.chord_id for chord in chart.chords] == [0, 0, 1]
    assert chart.chords[0].shape == chart.chords[1].shape
    assert chart.chords[2].shape != chart.chords[0].shape


def test_unresolved_midi_style_note_is_preserved_for_review() -> None:
    source = _source([_note(0.0, None, None, 64, verified=False)])
    chart = build_guitar_authoring_chart(source, _alignment("a" * 64), arrangement="lead")

    assert chart.single_notes == []
    assert chart.chords == []
    assert chart.unresolved_notes[0].reason == "string_fret_unresolved"
    assert any("not exportable" in warning for warning in chart.warnings)


def test_rejects_string_fret_pitch_mismatch_without_silent_repair() -> None:
    source = _source([_note(0.0, 0, 3, 44)])
    chart = build_guitar_authoring_chart(source, _alignment("a" * 64), arrangement="lead")
    assert chart.unresolved_notes[0].reason == "string_fret_pitch_mismatch"


def test_duplicate_string_polyphony_is_reviewed_not_chorded() -> None:
    source = _source([
        _note(0.0, 0, 3, 43),
        _note(0.0, 0, 5, 45),
    ])
    chart = build_guitar_authoring_chart(source, _alignment("a" * 64), arrangement="lead")
    assert chart.chords == []
    assert len(chart.unresolved_notes) == 2
    assert all(item.reason == "duplicate_string_in_simultaneous_group" for item in chart.unresolved_notes)


def test_unverified_source_positions_remain_review_required() -> None:
    source = _source([_note(0.0, 0, 3, 43, verified=False)])
    chart = build_guitar_authoring_chart(source, _alignment("a" * 64), arrangement="lead")
    assert chart.single_notes[0].review_required is True


def test_rejects_wrong_arrangement_tuning_alignment_and_sha() -> None:
    source = _source([_note(0.0, 0, 3, 43)])
    with pytest.raises(ValueError, match="exactly one rhythm"):
        build_guitar_authoring_chart(source, _alignment("a" * 64), arrangement="rhythm")

    bad_sha = _alignment("b" * 64)
    with pytest.raises(ValueError, match="SHA-256"):
        build_guitar_authoring_chart(source, bad_sha, arrangement="lead")

    wrong_track = _alignment("a" * 64, track_index=3)
    with pytest.raises(ValueError, match="track index"):
        build_guitar_authoring_chart(source, wrong_track, arrangement="lead")

    source.tracks[0].tuning_midi = [40, 45, 50, 55]
    with pytest.raises(ValueError, match="six-string"):
        build_guitar_authoring_chart(source, _alignment("a" * 64), arrangement="lead")
