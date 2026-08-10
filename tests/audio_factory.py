from __future__ import annotations

import math
import wave
from pathlib import Path


def _write_pcm16_mono(path: Path, signal: list[float], sample_rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    peak = max((abs(value) for value in signal), default=1.0) or 1.0
    scale = 0.92 / max(1.0, peak)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        frames = bytearray()
        for value in signal:
            sample = max(-32767, min(32767, int(value * scale * 32767)))
            frames.extend(sample.to_bytes(2, byteorder="little", signed=True))
        handle.writeframes(bytes(frames))


def write_click_track(
    path: Path,
    *,
    bpm: float = 120.0,
    beats: int = 24,
    sample_rate: int = 44100,
) -> list[float]:
    """Write a redistribution-safe synthetic click track and return ground-truth beat times."""
    interval = 60.0 / bpm
    beat_times = [0.25 + index * interval for index in range(beats)]
    duration = beat_times[-1] + 0.75
    total_samples = int(duration * sample_rate)
    signal = [0.0] * total_samples

    click_length = int(0.035 * sample_rate)
    for beat_time in beat_times:
        start = int(beat_time * sample_rate)
        for offset in range(click_length):
            index = start + offset
            if index >= total_samples:
                break
            envelope = math.exp(-8.0 * offset / click_length)
            signal[index] += 0.85 * envelope * math.sin(
                2.0 * math.pi * 1600.0 * offset / sample_rate
            )

    _write_pcm16_mono(path, signal, sample_rate)
    return beat_times


def write_synthetic_bass_phrase(
    path: Path,
    *,
    midi_notes: tuple[int, ...] = (40, 43, 45, 47, 48, 47, 45, 43),
    note_seconds: float = 0.65,
    gap_seconds: float = 0.15,
    sample_rate: int = 44100,
) -> list[tuple[float, float, int]]:
    """Write a synthetic plucked-bass phrase and return exact note ground truth."""
    first_start = 0.25
    stride = note_seconds + gap_seconds
    events = [
        (first_start + index * stride, note_seconds, midi)
        for index, midi in enumerate(midi_notes)
    ]
    duration = events[-1][0] + note_seconds + 0.35
    signal = [0.0] * int(duration * sample_rate)

    for start_time, note_duration, midi in events:
        fundamental = 440.0 * (2.0 ** ((midi - 69) / 12.0))
        start = int(start_time * sample_rate)
        length = int(note_duration * sample_rate)
        attack_samples = max(1, int(0.012 * sample_rate))

        for offset in range(length):
            index = start + offset
            if index >= len(signal):
                break
            time = offset / sample_rate
            attack = min(1.0, offset / attack_samples)
            decay = math.exp(-2.7 * time / note_duration)
            envelope = attack * decay
            phase = 2.0 * math.pi * fundamental * time
            sample = (
                math.sin(phase)
                + 0.42 * math.sin(2.0 * phase)
                + 0.18 * math.sin(3.0 * phase)
            )
            signal[index] += 0.55 * envelope * sample

    _write_pcm16_mono(path, signal, sample_rate)
    return events
