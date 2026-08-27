from __future__ import annotations

import pytest

from rocksmith_cdlc_generator.alignment import AlignmentAnchor, AlignmentRegion, AlignmentReport
from rocksmith_cdlc_generator.eof_recording_clock import (
    EOFRecordingClockFixture,
    EOFRecordingClockObservation,
    compare_source_to_eof_recording_clock,
)
from rocksmith_cdlc_generator.score_source import ArrangementRole
from rocksmith_cdlc_generator.source_import import (
    ImportedSource,
    SourceNoteEvent,
    SourceProvenance,
    SourceTempoEvent,
    SourceTimeSignatureEvent,
    SourceTrack,
    SourceTrustClass,
)


def _note(start: float, fret: int) -> SourceNoteEvent:
    return SourceNoteEvent(
        start_seconds=start,
        duration_seconds=0.25,
        midi=40 + fret,
        string_index=1,
        fret=fret,
        import_confidence=1.0,
        trust_class=SourceTrustClass.symbolic_unverified,
    )


def _source() -> ImportedSource:
    return ImportedSource(
        provenance=SourceProvenance(
            source_type="gp5",
            source_filename="fixture.gp5",
            source_sha256="a" * 64,
            importer="fixture",
            importer_version="1",
        ),
        tempo_events=[SourceTempoEvent(tick=0, time_seconds=0.0, bpm=120.0)],
        time_signatures=[
            SourceTimeSignatureEvent(
                tick=0,
                time_seconds=0.0,
                numerator=4,
                denominator=4,
            )
        ],
        beat_times_seconds=[float(index) * 0.5 for index in range(80)],
        tracks=[
            SourceTrack(
                source_track_index=1,
                name="Lead",
                instrument="lead",
                tuning_midi=[40, 45, 50, 55, 59, 64],
                notes=[_note(4.0, 8), _note(8.0, 9), _note(12.0, 10)],
            )
        ],
    )


def _alignment(*, offset: float) -> AlignmentReport:
    anchors = [
        AlignmentAnchor(
            source_time_seconds=float(source),
            audio_time_seconds=float(source) + offset,
            source_beat_index=source,
            audio_beat_index=source,
            confidence=0.9,
        )
        for source in (0, 10, 20, 30)
    ]
    return AlignmentReport(
        source_path="fixture.json",
        source_sha256="a" * 64,
        recording_sha256="b" * 64,
        track_index=1,
        audio_beat_start_index=0,
        global_offset_seconds=offset,
        anchor_stride_beats=10,
        matched_beats=31,
        rms_residual_seconds=0.0,
        median_abs_residual_seconds=0.0,
        max_abs_residual_seconds=0.0,
        confidence=0.9,
        anchors=anchors,
        regions=[
            AlignmentRegion(
                source_start_seconds=left.source_time_seconds,
                source_end_seconds=right.source_time_seconds,
                audio_start_seconds=left.audio_time_seconds,
                audio_end_seconds=right.audio_time_seconds,
                rms_residual_seconds=0.0,
                max_abs_residual_seconds=0.0,
                confidence=0.9,
            )
            for left, right in zip(anchors, anchors[1:])
        ],
    )


def _fixture(times: list[float]) -> EOFRecordingClockFixture:
    return EOFRecordingClockFixture(
        fixture_id="recording-clock-reference",
        score_sha256="a" * 64,
        recording_sha256="b" * 64,
        source_track_index=1,
        instrument=ArrangementRole.lead,
        eof_version="1.8RC14",
        evidence_note="Sparse local EOF observations against the same recording.",
        observations=[
            EOFRecordingClockObservation(
                event_index=index,
                eof_recording_time_seconds=time,
                score_bar=3 + index * 2,
                string_index=1,
                fret=8 + index,
            )
            for index, time in enumerate(times)
        ],
    )


def test_constant_two_bar_late_mapping_is_reported_on_recording_clock() -> None:
    source = _source()
    # At 120 BPM in 4/4, four seconds is exactly two bars.
    report = compare_source_to_eof_recording_clock(
        source,
        _alignment(offset=4.0),
        _fixture([4.0, 8.0, 12.0]),
    )

    assert report.classification == "constant_offset"
    assert report.first_playable_delta_seconds == pytest.approx(4.0)
    assert report.median_abs_error_seconds == pytest.approx(4.0)
    assert report.max_abs_error_seconds == pytest.approx(4.0)
    assert report.delta_spread_seconds == pytest.approx(0.0)
    assert [item.estimated_bar_delta for item in report.results] == pytest.approx([2.0, 2.0, 2.0])


def test_changing_delta_across_observations_is_classified_as_drift() -> None:
    source = _source()
    # Current mapping is source time; EOF observations diverge increasingly later.
    report = compare_source_to_eof_recording_clock(
        source,
        _alignment(offset=0.0),
        _fixture([4.0, 7.7, 11.2]),
    )

    assert report.classification == "drift"
    assert report.delta_spread_seconds == pytest.approx(0.8)
    assert report.max_abs_error_seconds == pytest.approx(0.8)


def test_single_observation_is_explicitly_insufficient_for_offset_vs_drift() -> None:
    source = _source()
    fixture = _fixture([4.0]).model_copy(
        update={"observations": [_fixture([4.0]).observations[0]]}
    )
    report = compare_source_to_eof_recording_clock(source, _alignment(offset=0.0), fixture)

    assert report.classification == "insufficient"
    assert report.max_abs_error_seconds == pytest.approx(0.0)


def test_fixture_fails_closed_for_stale_recording_hash() -> None:
    source = _source()
    fixture = _fixture([4.0, 8.0, 12.0]).model_copy(
        update={"recording_sha256": "c" * 64}
    )

    with pytest.raises(ValueError, match="stale for the current recording"):
        compare_source_to_eof_recording_clock(source, _alignment(offset=0.0), fixture)


def test_position_fingerprint_prevents_comparing_wrong_source_event() -> None:
    source = _source()
    fixture = _fixture([4.0, 8.0, 12.0])
    wrong = fixture.observations[0].model_copy(update={"fret": 7})
    fixture = fixture.model_copy(update={"observations": [wrong, *fixture.observations[1:]]})

    with pytest.raises(ValueError, match="identifies the wrong event"):
        compare_source_to_eof_recording_clock(source, _alignment(offset=0.0), fixture)
