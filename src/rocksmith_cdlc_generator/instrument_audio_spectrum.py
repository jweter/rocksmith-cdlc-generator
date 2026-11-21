"""Measured short-time spectral evidence for the selected instrument review event.

A visualization of local frequency energy, not a source separator or validated
fundamental/pitch detector. Compute on a worker thread, never Tk's playback poll.
"""
from __future__ import annotations

from array import array
from dataclasses import dataclass
import math
from pathlib import Path
import wave


@dataclass(frozen=True)
class SpectrumSample:
    center_seconds: float
    frequencies_hz: tuple[float, ...]
    relative_magnitudes: tuple[float, ...]
    sample_rate_hz: int


def measure_spectrum(
    audio_path: Path,
    center_seconds: float,
    *,
    bins: int = 36,
    minimum_hz: float = 25.0,
    maximum_hz: float = 4000.0,
    window_seconds: float = 0.18,
) -> SpectrumSample:
    """Windowed Goertzel spectrum at log-spaced frequencies.

    Uses stdlib PCM operations for an optional-DSP-dependency-free review view.
    Selects the higher-energy stereo channel so out-of-phase channels do not
    produce a false silence. This is diagnostic, not note evidence authority.
    """
    if not math.isfinite(center_seconds) or center_seconds < 0:
        raise ValueError("Spectrum time must be a nonnegative finite second")
    if not 12 <= bins <= 96 or minimum_hz <= 0 or maximum_hz <= minimum_hz:
        raise ValueError("Invalid spectral frequency grid")
    if not 0.06 <= window_seconds <= 0.4:
        raise ValueError("Spectrum window must be 60–400 ms")
    with wave.open(str(audio_path), "rb") as src:
        if src.getsampwidth() != 2 or src.getcomptype() != "NONE":
            raise ValueError("Spectrum requires uncompressed 16-bit WAV")
        rate, channels, total = src.getframerate(), src.getnchannels(), src.getnframes()
        if channels not in (1, 2) or rate <= 0 or total <= 0:
            raise ValueError("Invalid spectral audio source")
        if maximum_hz >= rate / 2:
            raise ValueError("Spectral grid must remain below Nyquist")
        count = min(total, max(1, round(rate * window_seconds)))
        center = min(max(round(center_seconds * rate), 0), total - 1)
        start = max(0, min(center - count // 2, total - count))
        src.setpos(start)
        samples = array("h")
        samples.frombytes(src.readframes(count))
    count = len(samples) // channels
    if count < 4:
        raise ValueError("Spectrum input too short")
    if channels == 1:
        sequence = list(samples)
    else:
        energy = [0, 0]
        for i in range(0, count * 2, 2):
            energy[0] += samples[i] ** 2
            energy[1] += samples[i + 1] ** 2
        best = 0 if energy[0] >= energy[1] else 1
        sequence = [samples[i * 2 + best] for i in range(count)]
    offset = sum(sequence) / count
    weighted = [
        (value - offset) * (0.5 - 0.5 * math.cos(2.0 * math.pi * i / (count - 1)))
        for i, value in enumerate(sequence)
    ]
    frequencies = tuple(
        minimum_hz * (maximum_hz / minimum_hz) ** (i / (bins - 1))
        for i in range(bins)
    )
    raw: list[float] = []
    for frequency in frequencies:
        coefficient = 2.0 * math.cos(2.0 * math.pi * frequency / rate)
        previous = earlier = 0.0
        for value in weighted:
            current = value + coefficient * previous - earlier
            earlier, previous = previous, current
        power = max(0.0, previous * previous + earlier * earlier - coefficient * previous * earlier)
        raw.append(math.sqrt(power))
    scale = max(max(raw), 1e-12)
    return SpectrumSample(
        center_seconds=center_seconds,
        frequencies_hz=frequencies,
        relative_magnitudes=tuple(value / scale for value in raw),
        sample_rate_hz=rate,
    )
