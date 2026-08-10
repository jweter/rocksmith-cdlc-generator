from pathlib import Path

import pytest

from rocksmith_cdlc_generator.alignment import align_source_to_tempo_map, map_source_time
from rocksmith_cdlc_generator.beats import BeatEvent, TempoMap
from rocksmith_cdlc_generator.source_import import (
    ImportedSource,
    SourceNoteEvent,
    SourceProvenance,
    SourceTempoEvent,
    SourceTrack,
)


def _source() -> ImportedSource:
    return ImportedSource(
        provenance=SourceProvenance(
            source_type="midi",
            source_filename="bass.mid",
            source_sha256="a" * 64,
            importer="test",
            importer_version="1",
        ),
        tempo_events=[SourceTempoEvent(tick=0, time_seconds=0.0, bpm=120.0)],
        tracks=[
            SourceTrack(
                source_track_index=2,
                name="Bass",
                instrument="bass",
                notes=[
                    SourceNoteEvent(
                        start_seconds=i * 0.5,
                        duration_seconds=0.25,
                        midi=40,
                        import_confidence=1.0,
                    )
                    for i in range(24)
                ],
            )
        ],
    )


def _tempo_map(offset: float = 1.25, drift: float = 0.0) -> TempoMap:
    beats = []
    time = offset
    for i in range(24):
        beats.append(
            BeatEvent(
                time=time,
                beat=i % 4 + 1,
                measure=i // 4 + 1,
                bpm=120.0,
                confidence=0.95,
                is_downbeat=i % 4 == 0,
            )
        )
        time += 0.5 + drift * i
    return TempoMap(engine="synthetic", beats=beats)


def test_alignment_recovers_global_offset_and_is_monotonic() -> None:
    report = align_source_to_tempo_map(
        _source(),
        _tempo_map(),
        source_path=Path("bass.json"),
        track_index=2,
        audio_beat_index=0,
        anchor_stride_beats=4,
    )
    assert report.global_offset_seconds == pytest.approx(1.25)
    assert report.median_abs_residual_seconds == pytest.approx(0.0, abs=1e-9)
    mapped = [map_source_time(report, value) for value in (0.0, 1.0, 2.0, 4.0)]
    assert mapped == sorted(mapped)
    assert mapped[2] == pytest.approx(3.25)


def test_piecewise_anchors_follow_live_tempo_drift() -> None:
    report = align_source_to_tempo_map(
        _source(),
        _tempo_map(drift=0.0015),
        source_path=Path("bass.json"),
        track_index=2,
        audio_beat_index=0,
        anchor_stride_beats=4,
    )
    assert len(report.anchors) > 2
    assert report.max_abs_residual_seconds < 0.02
    assert report.confidence > 0.70


def test_automatic_start_search_can_skip_intro_beats() -> None:
    tempo = _tempo_map()
    intro = [
        BeatEvent(time=0.10 + i * 0.65, beat=i % 4 + 1, measure=1, bpm=92.3, confidence=0.8)
        for i in range(4)
    ]
    shifted = []
    base = intro[-1].time + 0.65
    for i, beat in enumerate(tempo.beats):
        shifted.append(beat.model_copy(update={"time": base + i * 0.5, "measure": i // 4 + 2}))
    report = align_source_to_tempo_map(
        _source(),
        TempoMap(engine="synthetic", beats=intro + shifted),
        source_path=Path("bass.json"),
        track_index=2,
        anchor_stride_beats=4,
    )
    assert report.audio_beat_start_index == 4
    assert report.global_offset_seconds == pytest.approx(base)


def test_rejects_bad_explicit_audio_beat_index() -> None:
    with pytest.raises(ValueError, match="outside"):
        align_source_to_tempo_map(
            _source(),
            _tempo_map(),
            source_path=Path("bass.json"),
            track_index=2,
            audio_beat_index=999,
        )
