import pytest

from rocksmith_cdlc_generator.deterministic_tempo_map import (
    TempoChange,
    build_deterministic_tempo_map,
)


def test_constant_tempo_4_4() -> None:
    tempo_map = build_deterministic_tempo_map(measure_count=2, bpm=120.0)

    assert len(tempo_map.beats) == 8
    assert tempo_map.time_signature_numerator == 4
    assert tempo_map.time_signature_denominator == 4

    first = tempo_map.beats[0]
    assert first.time == pytest.approx(0.0)
    assert first.measure == 1
    assert first.beat == 1
    assert first.is_downbeat is True

    second_measure_downbeat = tempo_map.beats[4]
    assert second_measure_downbeat.measure == 2
    assert second_measure_downbeat.beat == 1
    assert second_measure_downbeat.is_downbeat is True
    assert second_measure_downbeat.time == pytest.approx(2.0)

    non_downbeats = [beat for beat in tempo_map.beats if not beat.is_downbeat]
    assert all(beat.beat != 1 for beat in non_downbeats)


def test_beat_spacing_matches_bpm() -> None:
    tempo_map = build_deterministic_tempo_map(measure_count=1, bpm=120.0)
    times = [beat.time for beat in tempo_map.beats]
    deltas = [second - first for first, second in zip(times, times[1:])]
    assert deltas == pytest.approx([0.5, 0.5, 0.5])


def test_denominator_scales_beat_duration() -> None:
    quarter_time = build_deterministic_tempo_map(
        measure_count=1, bpm=120.0, time_signature_numerator=4, time_signature_denominator=4
    )
    eighth_time = build_deterministic_tempo_map(
        measure_count=1, bpm=120.0, time_signature_numerator=6, time_signature_denominator=8
    )
    assert quarter_time.beats[1].time == pytest.approx(0.5)
    assert eighth_time.beats[1].time == pytest.approx(0.25)


def test_tempo_change_takes_effect_at_measure() -> None:
    tempo_map = build_deterministic_tempo_map(
        measure_count=3,
        bpm=120.0,
        tempo_changes=[TempoChange(measure=2, bpm=60.0)],
    )
    measure_1_beats = [beat for beat in tempo_map.beats if beat.measure == 1]
    measure_2_beats = [beat for beat in tempo_map.beats if beat.measure == 2]
    assert all(beat.bpm == pytest.approx(120.0) for beat in measure_1_beats)
    assert all(beat.bpm == pytest.approx(60.0) for beat in measure_2_beats)

    measure_2_start = measure_2_beats[0].time
    measure_2_second_beat = measure_2_beats[1].time
    assert measure_2_second_beat - measure_2_start == pytest.approx(1.0)


def test_rejects_non_positive_measure_count() -> None:
    with pytest.raises(ValueError):
        build_deterministic_tempo_map(measure_count=0, bpm=120.0)


def test_rejects_tempo_change_beyond_measure_count() -> None:
    with pytest.raises(ValueError):
        build_deterministic_tempo_map(
            measure_count=2,
            bpm=120.0,
            tempo_changes=[TempoChange(measure=5, bpm=100.0)],
        )


def test_map_round_trips_through_tempo_map_validation() -> None:
    tempo_map = build_deterministic_tempo_map(measure_count=4, bpm=95.0)
    assert tempo_map.median_bpm == pytest.approx(95.0)
