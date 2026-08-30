from array import array
from pathlib import Path
import wave

import pytest

from rocksmith_cdlc_generator.click_track_render import render_click_track_wav
from rocksmith_cdlc_generator.deterministic_tempo_map import build_deterministic_tempo_map


def _read_samples(path: Path) -> array:
    with wave.open(str(path), "rb") as handle:
        assert handle.getnchannels() == 1
        assert handle.getsampwidth() == 2
        samples = array("h")
        samples.frombytes(handle.readframes(handle.getnframes()))
        return samples


def test_render_produces_mono_16bit_wav(tmp_path: Path) -> None:
    tempo_map = build_deterministic_tempo_map(measure_count=2, bpm=120.0)
    destination = tmp_path / "click.wav"

    render_click_track_wav(tempo_map, destination, count_in_measures=1, trailing_seconds=0.1)

    with wave.open(str(destination), "rb") as handle:
        assert handle.getnchannels() == 1
        assert handle.getsampwidth() == 2
        assert handle.getframerate() == tempo_map.sample_rate_hz


def test_chart_downbeat_lands_exactly_after_count_in(tmp_path: Path) -> None:
    tempo_map = build_deterministic_tempo_map(measure_count=1, bpm=120.0)
    destination = tmp_path / "click.wav"
    sample_rate = tempo_map.sample_rate_hz

    render_click_track_wav(tempo_map, destination, count_in_measures=2, trailing_seconds=0.1)
    samples = _read_samples(destination)

    # 2 measures of 4/4 count-in at 120 BPM (0.5s/beat) = 4.0s before the chart's beat 1.
    expected_frame = int(round(4.0 * sample_rate))
    # The synthesized click is a decaying sine burst; its peak-magnitude sample should
    # fall within the burst window immediately at/after the expected onset frame.
    window = samples[expected_frame : expected_frame + int(sample_rate * 0.025)]
    assert any(abs(sample) > 1000 for sample in window)
    # Silence should hold well before the expected onset (no drift/early trigger).
    quiet_window = samples[expected_frame - 2000 : expected_frame - 200]
    assert all(abs(sample) < 50 for sample in quiet_window)


def test_measure_boundaries_stay_aligned_across_full_arrangement(tmp_path: Path) -> None:
    tempo_map = build_deterministic_tempo_map(measure_count=8, bpm=140.0)
    destination = tmp_path / "click.wav"
    sample_rate = tempo_map.sample_rate_hz

    render_click_track_wav(tempo_map, destination, count_in_measures=2, trailing_seconds=0.2)
    samples = _read_samples(destination)

    seconds_per_beat = 60.0 / 140.0
    count_in_seconds = 2 * 4 * seconds_per_beat

    downbeats = [beat for beat in tempo_map.beats if beat.is_downbeat]
    for beat in downbeats:
        expected_frame = int(round((count_in_seconds + beat.time) * sample_rate))
        window = samples[expected_frame : expected_frame + int(sample_rate * 0.025)]
        assert any(abs(sample) > 1000 for sample in window), (
            f"Expected an audible downbeat click at measure {beat.measure}"
        )


def test_rejects_unsupported_subdivision(tmp_path: Path) -> None:
    tempo_map = build_deterministic_tempo_map(measure_count=1, bpm=120.0)
    with pytest.raises(ValueError):
        render_click_track_wav(tempo_map, tmp_path / "click.wav", subdivision="thirty-second")


def test_rejects_negative_count_in(tmp_path: Path) -> None:
    tempo_map = build_deterministic_tempo_map(measure_count=1, bpm=120.0)
    with pytest.raises(ValueError):
        render_click_track_wav(tempo_map, tmp_path / "click.wav", count_in_measures=-1)


def test_subdivision_adds_extra_clicks_between_beats(tmp_path: Path) -> None:
    tempo_map = build_deterministic_tempo_map(measure_count=1, bpm=120.0)
    sample_rate = tempo_map.sample_rate_hz
    seconds_per_beat = 60.0 / 120.0

    plain = tmp_path / "plain.wav"
    subdivided = tmp_path / "subdivided.wav"
    render_click_track_wav(tempo_map, plain, count_in_measures=0, trailing_seconds=0.1)
    render_click_track_wav(
        tempo_map, subdivided, count_in_measures=0, subdivision="eighth", trailing_seconds=0.1
    )

    plain_samples = _read_samples(plain)
    subdivided_samples = _read_samples(subdivided)

    midpoint_frame = int(round((seconds_per_beat / 2.0) * sample_rate))
    window_plain = plain_samples[midpoint_frame : midpoint_frame + int(sample_rate * 0.025)]
    window_subdivided = subdivided_samples[
        midpoint_frame : midpoint_frame + int(sample_rate * 0.025)
    ]
    assert all(abs(sample) < 50 for sample in window_plain)
    assert any(abs(sample) > 500 for sample in window_subdivided)
