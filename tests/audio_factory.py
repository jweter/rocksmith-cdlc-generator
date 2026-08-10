from __future__ import annotations

import math
import wave
from pathlib import Path


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
            signal[index] += 0.85 * envelope * math.sin(2.0 * math.pi * 1600.0 * offset / sample_rate)

    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        frames = bytearray()
        for value in signal:
            sample = max(-32767, min(32767, int(value * 32767)))
            frames.extend(sample.to_bytes(2, byteorder="little", signed=True))
        handle.writeframes(bytes(frames))
    return beat_times
