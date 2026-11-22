"""Conservative, read-only long-window harmonic pattern evidence for Bass.

Unlike the 180-ms display spectrum, this uses two independently stationary
long windows, explicitly confirmed tuning, and nearby semitone/octave
competitors. It provides diagnostic evidence only: never transcription,
source separation or automatic score promotion.
"""
from __future__ import annotations

from array import array
from dataclasses import dataclass
from math import cos, isfinite, pi, sqrt
from pathlib import Path
import sys
import wave

from .hashing import sha256_file
from .instrument_audio_focus import candidate_positions, focus_profile, midi_frequency

# Diagnostic-only octave-leakage negative, not an instrument classifier.
MIN_ROOT_TO_OCTAVE_PARTIAL = 0.55


@dataclass(frozen=True)
class BassHarmonicEvidence:
    status: str  # plausible_pattern / ambiguous / insufficient_signal / unplayable / unavailable
    expected_midi: int
    source_sha256: str | None
    observed_windows: int
    strongest_competitor_midi: int | None
    minimum_candidate_margin: float | None
    candidate_fundamental_hz: float | None
    minimum_root_to_octave_ratio: float | None = None
    octave_leakage_negative: bool = False
    source_isolation_proven: bool = False
    note_pitch_verified: bool = False
    recording_timing_verified: bool = False
    score_authority_changed: bool = False


def _goertzel(weighted: list[float], frequency: float, rate: int) -> float:
    coefficient = 2.0 * cos(2.0 * pi * frequency / rate)
    previous = earlier = 0.0
    for value in weighted:
        current = value + coefficient * previous - earlier
        earlier, previous = previous, current
    power = max(0.0, previous * previous + earlier * earlier
                - coefficient * previous * earlier)
    return sqrt(power)


def _harmonic_signature(weighted: list[float], note: int, rate: int) -> tuple[float, float, int, float]:
    fundamental = midi_frequency(note)
    if fundamental * 4 >= rate / 2:
        return 0.0, 0.0, 0, 0.0
    magnitudes = [_goertzel(weighted, fundamental * harmonic, rate) for harmonic in range(1, 5)]
    top = max(magnitudes)
    if top <= 1e-9:
        return 0.0, 0.0, 0, 0.0
    supported = sum(m >= .12 * top for m in magnitudes)
    # A strong upper octave must not borrow 3xE1/4xE1 energy to assert E1.
    root_to_octave = min(100.0, magnitudes[0] / max(magnitudes[1], 1e-9))
    return sum(magnitudes), magnitudes[0] / top, supported, root_to_octave


def _read_weighted_pcm(src: wave.Wave_read, start: int, frame_count: int) -> tuple[list[float], float]:
    src.setpos(start)
    raw = src.readframes(frame_count)
    channels = src.getnchannels()
    if len(raw) != frame_count * channels * 2:
        raise ValueError("Truncated measured audio window")
    samples = array("h")
    samples.frombytes(raw)
    if sys.byteorder != "little":
        samples.byteswap()
    if channels == 2:
        energy_left = sum(int(samples[2*i]) ** 2 for i in range(frame_count))
        energy_right = sum(int(samples[2*i+1]) ** 2 for i in range(frame_count))
        channel = 0 if energy_left >= energy_right else 1
        values = [samples[2*i+channel] for i in range(frame_count)]
    else:
        values = list(samples)
    average = sum(values) / frame_count
    variance = sum((v-average)**2 for v in values) / frame_count
    weighted = [
        (v-average) * (0.5 - 0.5*cos(2*pi*i/(frame_count-1)))
        for i, v in enumerate(values)
    ]
    return weighted, sqrt(variance)


def measure_bass_harmonic_pattern(
    audio_path: Path,
    *,
    expected_midi: int,
    tuning_midi: tuple[int, ...] | list[int] | None,
    note_start_seconds: float,
    note_duration_seconds: float,
    window_seconds: float = .65,
    highest_fret: int = 24,
) -> BassHarmonicEvidence:
    """Inspect two disjoint windows; don't infer a note from a single spectrum.

    A pattern match can be caused by another instrument occupying the same
    frequencies. Thus even 'plausible_pattern' remains review-only.
    """
    if not (isfinite(note_start_seconds) and note_start_seconds >= 0
            and isfinite(note_duration_seconds) and note_duration_seconds > 0):
        raise ValueError("Note time and duration must be positive finite seconds")
    if not .55 <= window_seconds <= .9:
        raise ValueError("Long Bass evidence window must be 0.55–0.9 seconds")
    midi_frequency(expected_midi)
    def evidence(status: str, source_hash=None, count=0, competitor=None, margin=None,
                 root_octave=None, octave_negative=False):
        return BassHarmonicEvidence(
            status, expected_midi, source_hash, count, competitor, margin,
            round(midi_frequency(expected_midi), 3),
            round(root_octave, 3) if root_octave is not None else None,
            octave_negative,
        )
    try:
        if tuning_midi is None:
            return evidence("unplayable")
        focus_profile("bass", tuning_midi, highest_fret=highest_fret)
        if not candidate_positions(expected_midi, tuning_midi, highest_fret=highest_fret):
            return evidence("unplayable")
    except (ValueError, RuntimeError):
        return evidence("unplayable")
    if note_duration_seconds < 2 * window_seconds + .10:
        return evidence("insufficient_signal")

    path = Path(audio_path)
    try:
        source_hash = sha256_file(path)
        with wave.open(str(path), "rb") as src:
            if src.getsampwidth() != 2 or src.getcomptype() != "NONE":
                return evidence("unavailable")
            rate, channels, frames = src.getframerate(), src.getnchannels(), src.getnframes()
            if channels not in (1,2) or rate < 8000 or frames <= 0:
                return evidence("unavailable")
            # A valid RIFF header can lie about the final PCM frame when the
            # file was truncated. Never report a positive diagnostic on it.
            src.setpos(frames - 1)
            if len(src.readframes(1)) != channels * 2:
                return evidence("unavailable")
            width = round(window_seconds*rate)
            first = round((note_start_seconds + .05) * rate)
            last = round((note_start_seconds + note_duration_seconds - .05 - window_seconds)*rate)
            if first < 0 or last-first < width or last+width > frames:
                return evidence("insufficient_signal")
            competitors = [
                note for note in (expected_midi-12, expected_midi-1,
                                  expected_midi+1, expected_midi+12)
                if 0 <= note <= 127 and note != expected_midi
                and candidate_positions(note, tuning_midi, highest_fret=highest_fret)
            ]
            if not competitors:
                return evidence("ambiguous")
            strongest = None
            margins: list[float] = []
            octave_ratios: list[float] = []
            for start in (first, last):
                samples, rms = _read_weighted_pcm(src, start, width)
                if rms < 100:
                    return evidence("insufficient_signal", source_hash)
                candidate, root_fraction, support, root_octave = _harmonic_signature(samples, expected_midi, rate)
                scores = [(_harmonic_signature(samples, note, rate)[0], note) for note in competitors]
                rival, rival_midi = max(scores)
                if candidate <= 1e-9 or root_fraction < .25 or support < 2:
                    return evidence("ambiguous", source_hash, competitor=rival_midi,
                                    root_octave=root_octave)
                if root_octave < MIN_ROOT_TO_OCTAVE_PARTIAL:
                    return evidence("ambiguous", source_hash, competitor=rival_midi,
                                    root_octave=root_octave, octave_negative=True)
                octave_ratios.append(root_octave)
                if rival <= 1e-9:
                    margin = 100.0
                else:
                    margin = candidate / rival
                margins.append(margin)
                if strongest is None or rival > strongest[0]:
                    strongest = (rival, rival_midi)
            if sha256_file(path) != source_hash:
                return evidence("unavailable")
            minimum = min(margins)
            return evidence(
                "plausible_pattern" if minimum >= 1.75 else "ambiguous",
                source_hash, 2, strongest[1] if strongest else None, round(minimum, 3),
                root_octave=min(octave_ratios),
            )
    except (OSError, ValueError, EOFError, wave.Error):
        return evidence("unavailable")
