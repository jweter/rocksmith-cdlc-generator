"""Bounded silence/transient-only negative screen for Bass stem trust.

A matching stem receipt, different waveform, and convincing note confidence
cannot establish that the stem actually contains Bass. This screen catches
obvious no-sustained-content negatives *before* a stem can be used as
independently verified note provenance. Sustained content does NOT prove Bass:
other instruments and continuous percussion may also survive this screen.

Reads only bounded 16-bit PCM windows from the explicitly supplied local file;
no model, subprocess, network, audio copy, or private file path in results.
"""
from __future__ import annotations

from array import array
from dataclasses import dataclass
import math
from pathlib import Path
import sys
import wave

SEGMENT_SECONDS = 0.01
SEGMENTS_PER_WINDOW = 48
MAX_WINDOWS = 12
MIN_ACTIVE_RMS = 100.0
RELATIVE_ACTIVE_FRACTION = 0.22
MIN_CONSECUTIVE_ACTIVE = 32


@dataclass(frozen=True)
class BassNegativeSignalScreen:
    status: str  # not_obviously_negative, silence_only, transient_only, unavailable
    inspected_windows: int
    sustained_windows: int
    transient_windows: int
    source_isolation_proven: bool = False
    bass_instrument_proven: bool = False
    note_pitch_verified: bool = False
    musical_pass_proven: bool = False

    @property
    def not_obviously_negative(self) -> bool:
        return self.status == "not_obviously_negative"


def _rms_by_channel(samples: array, first: int, count: int, channels: int) -> float:
    """Remove DC before measuring a signal: an offset is not musical content."""
    loudest = 0.0
    for channel in range(channels):
        total = 0
        power = 0
        for pos in range(first * channels + channel,
                         (first + count) * channels, channels):
            value = samples[pos]
            total += value
            power += value * value
        mean = total / count
        variance = max(0.0, power / count - mean * mean)
        loudest = max(loudest, math.sqrt(variance))
    return loudest


def screen_bass_stem_obvious_negatives(audio_path: Path) -> BassNegativeSignalScreen:
    """Require a small sustained-content region, not merely a drum attack.

    Each of up to 12 distributed 0.48-second PCM windows is divided into 48
    10-ms sections. At least 32 consecutive sections must carry actual
    varying audio above both an absolute floor and a local peak fraction.
    Fine-grained continuity is essential: two 55-ms kicks that straddle
    80-ms bins must never combine into false 320-ms sustained evidence.
    Silence and a series of isolated transient percussion attacks are
    rejected; sustained unrelated material remains explicitly *unverified*.
    """
    def report(status: str, measured: int, sustained: int, transients: int):
        return BassNegativeSignalScreen(status, measured, sustained, transients)

    try:
        with wave.open(str(Path(audio_path)), "rb") as src:
            rate = src.getframerate()
            channels = src.getnchannels()
            frames = src.getnframes()
            if (src.getsampwidth() != 2 or src.getcomptype() != "NONE"
                    or rate < 8000 or rate > 192000 or channels not in (1, 2)):
                return report("unavailable", 0, 0, 0)
            segment_frames = round(rate * SEGMENT_SECONDS)
            window_frames = segment_frames * SEGMENTS_PER_WINDOW
            if frames < window_frames or segment_frames <= 0:
                return report("unavailable", 0, 0, 0)
            # A RIFF header can claim frames that do not exist. A positive
            # instrument gate on truncated PCM would be false authority.
            src.setpos(frames - 1)
            if len(src.readframes(1)) != channels * 2:
                return report("unavailable", 0, 0, 0)
            positions = sorted({
                round(i * (frames - window_frames) / (MAX_WINDOWS - 1))
                for i in range(MAX_WINDOWS)
            })
            measured = sustained = transient = 0
            for start in positions:
                src.setpos(start)
                raw = src.readframes(window_frames)
                if len(raw) != window_frames * channels * 2:
                    return report("unavailable", measured, sustained, transient)
                samples = array("h")
                samples.frombytes(raw)
                if sys.byteorder != "little":
                    samples.byteswap()
                levels = [
                    _rms_by_channel(samples, j * segment_frames, segment_frames,
                                    channels)
                    for j in range(SEGMENTS_PER_WINDOW)
                ]
                peak = max(levels)
                measured += 1
                if peak < MIN_ACTIVE_RMS:
                    continue
                threshold = max(MIN_ACTIVE_RMS, peak * RELATIVE_ACTIVE_FRACTION)
                run = longest = 0
                for level in levels:
                    run = run + 1 if level >= threshold else 0
                    longest = max(longest, run)
                if longest >= MIN_CONSECUTIVE_ACTIVE:
                    sustained += 1
                else:
                    transient += 1
            if sustained:
                return report("not_obviously_negative", measured, sustained, transient)
            return report(
                "transient_only" if transient else "silence_only",
                measured, sustained, transient,
            )
    except (OSError, EOFError, ValueError, wave.Error, OverflowError):
        return report("unavailable", 0, 0, 0)
