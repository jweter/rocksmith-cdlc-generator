"""Octave-leakage *negative* evidence for score-matched Bass note candidates.

A strong octave overtone can convince an audio pitch estimator to emit the
lower score MIDI note, even when no lower fundamental is measured. Examine two
independent short, stationary windows for a reproducible octave-dominated
spectrum before promoting an otherwise eligible Bass candidate.

The outcome is a veto, never an independent positive proof of Bass pitch,
instrument identity, isolation, timing or gameplay. No model or network calls,
media exports, process identities or private filenames appear in the report.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from pathlib import Path
import wave

from .bass_harmonic_evidence import _goertzel, _read_weighted_pcm
from .instrument_audio_focus import midi_frequency

WINDOW_SECONDS = 0.32
EDGE_SECONDS = 0.05
MIN_RMS = 100.0
MIN_NORMALIZED_OCTAVE = 0.14
MIN_OCTAVE_TO_ROOT = 8.0


@dataclass(frozen=True)
class BassOctaveNegative:
    status: str  # octave_leakage, not_detected, insufficient_signal, unavailable
    observed_windows: int
    source_isolation_proven: bool = False
    bass_pitch_verified: bool = False
    score_authority_changed: bool = False

    @property
    def must_veto(self) -> bool:
        return self.status in {"octave_leakage", "unavailable"}


def inspect_bass_octave_leakage(
    audio_path: Path, *, expected_midi: int,
    note_start_seconds: float, note_duration_seconds: float,
) -> BassOctaveNegative:
    """Only flag *repeated, strong* octave energy with little lower fundamental.

    Two non-overlapping 320-ms Hann-windowed regions must both show octave
    content against the local overall signal and an >=8:1 octave/root ratio.
    One loud pick attack, random broadband noise, a short legitimate note,
    or a missing second observation does not become a positive note claim.
    The no-evidence case is explicitly insufficient, not a claimed clean PASS.
    """
    def result(status: str, windows: int = 0) -> BassOctaveNegative:
        return BassOctaveNegative(status=status, observed_windows=windows)

    if (type(expected_midi) is not int or not 0 <= expected_midi <= 127
            or type(note_start_seconds) not in (int, float)
            or type(note_duration_seconds) not in (int, float)
            or not isfinite(note_start_seconds) or note_start_seconds < 0
            or not isfinite(note_duration_seconds) or note_duration_seconds <= 0):
        raise ValueError("INVALID_BASS_OCTAVE_NEGATIVE_ARGUMENT")

    if note_duration_seconds < 2 * WINDOW_SECONDS + 2 * EDGE_SECONDS:
        return result("insufficient_signal")

    try:
        frequency = midi_frequency(expected_midi)
        with wave.open(str(Path(audio_path)), "rb") as src:
            rate = src.getframerate()
            channels = src.getnchannels()
            frames = src.getnframes()
            if (src.getsampwidth() != 2 or src.getcomptype() != "NONE"
                    or channels not in (1, 2) or rate < 8000 or rate > 192000
                    or frequency * 2 >= rate / 2 or frames <= 0):
                return result("unavailable")
            # Check for a WAV header claiming PCM frames that do not exist.
            src.setpos(frames - 1)
            if len(src.readframes(1)) != channels * 2:
                return result("unavailable")

            width = round(WINDOW_SECONDS * rate)
            first = round((note_start_seconds + EDGE_SECONDS) * rate)
            last = round(
                (note_start_seconds + note_duration_seconds
                 - EDGE_SECONDS - WINDOW_SECONDS) * rate
            )
            if first < 0 or last - first < width or last + width > frames:
                return result("insufficient_signal")

            inspected = 0
            for start in (first, last):
                weighted, rms = _read_weighted_pcm(src, start, width)
                if rms < MIN_RMS:
                    return result("insufficient_signal", inspected)
                root = _goertzel(weighted, frequency, rate)
                octave = _goertzel(weighted, 2 * frequency, rate)
                inspected += 1
                # A single broadband transient can put energy at both
                # frequencies. Require a strong stationary octave partial
                # *relative to local signal energy*, not merely root absence.
                relative_octave = octave / max(rms * width, 1e-12)
                if (relative_octave < MIN_NORMALIZED_OCTAVE
                        or octave < MIN_OCTAVE_TO_ROOT * root):
                    return result("not_detected", inspected)
            return result("octave_leakage", inspected)
    except (OSError, ValueError, OverflowError, EOFError, wave.Error):
        return result("unavailable")
