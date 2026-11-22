"""Independent, local PCM attack-onset evidence for candidate Bass notes.

Do not infer an attack from an estimator's MIDI, f0, or self-reported
confidence. A measured energy transition is a *necessary* per-note check for
automatic symbolic verification, not proof the source is a Bass instrument.

Bounds: 16-bit PCM, up to 270 ms for each candidate, no model or remote I/O.
A backtracked note boundary may precede its true energy transient by 80 ms.
"""
from __future__ import annotations

from array import array
from dataclasses import dataclass
from math import isfinite
from pathlib import Path
import sys
import wave

from .bass_negative_signal import _rms_by_channel

SEGMENT_SECONDS = 0.01
PRE_SECONDS = 0.12
POST_SECONDS = 0.15
MAX_DELAY_SECONDS = 0.08
MIN_ATTACK_RMS = 250.0
MIN_RMS_JUMP = 200.0
MIN_ATTACK_RATIO = 2.5
MIN_ATTACK_CONFIDENCE = 0.60


@dataclass(frozen=True)
class BassAttackEvidence:
    status: str  # attack_detected, no_attack, insufficient_signal, unavailable
    confidence: float = 0.0
    measured_onset_delta_seconds: float | None = None
    pre_attack_rms: float | None = None
    post_attack_rms: float | None = None
    source_isolation_proven: bool = False
    bass_pitch_verified: bool = False
    recording_clock_verified: bool = False
    musical_pass_proven: bool = False

    @property
    def independent_attack(self) -> bool:
        return (
            self.status == "attack_detected"
            and self.confidence >= MIN_ATTACK_CONFIDENCE
            and self.measured_onset_delta_seconds is not None
            and 0 <= self.measured_onset_delta_seconds <= MAX_DELAY_SECONDS
        )


def inspect_bass_attack_onset(
    audio_path: Path, *, note_start_seconds: float, note_duration_seconds: float,
) -> BassAttackEvidence:
    """Detect a sharp sustained local RMS increase near a claimed onset.

    Each 10-ms RMS uses per-channel DC-removal. Require a 30-ms post-attack
    plateau (not a single-sample click) relative to preceding 30-ms RMS.
    Candidate transitions are searched from the backtracked boundary through
    +80ms, but a steady low-frequency fundamental cannot count as an attack.
    The result cannot prove the signal was produced by Bass.
    """
    if (
        type(note_start_seconds) not in (int, float)
        or type(note_duration_seconds) not in (int, float)
        or not isfinite(note_start_seconds)
        or not isfinite(note_duration_seconds)
        or note_start_seconds < 0
        or note_duration_seconds <= 0
    ):
        raise ValueError("INVALID_BASS_ATTACK_ONSET_ARGUMENT")

    if note_start_seconds < PRE_SECONDS or note_duration_seconds < 0.10:
        return BassAttackEvidence("insufficient_signal")

    try:
        with wave.open(str(Path(audio_path)), "rb") as source:
            rate, channels, frames = (
                source.getframerate(), source.getnchannels(), source.getnframes()
            )
            if (
                source.getsampwidth() != 2
                or source.getcomptype() != "NONE"
                or channels not in (1, 2)
                or rate < 8000 or rate > 192000
                or frames <= 0
            ):
                return BassAttackEvidence("unavailable")
            segment_frames = round(rate * SEGMENT_SECONDS)
            if segment_frames <= 0:
                return BassAttackEvidence("unavailable")
            pre_segments = round(PRE_SECONDS / SEGMENT_SECONDS)
            post_segments = round(POST_SECONDS / SEGMENT_SECONDS)
            window_segments = pre_segments + post_segments
            onset_frame = round(note_start_seconds * rate)
            first_frame = onset_frame - segment_frames * pre_segments
            end_frame = first_frame + segment_frames * window_segments
            if first_frame < 0 or end_frame > frames:
                return BassAttackEvidence("insufficient_signal")

            # Malformed WAVs can declare PCM samples past the real EOF.
            source.setpos(frames - 1)
            if len(source.readframes(1)) != channels * 2:
                return BassAttackEvidence("unavailable")
            source.setpos(first_frame)
            raw = source.readframes(segment_frames * window_segments)
            if len(raw) != segment_frames * window_segments * channels * 2:
                return BassAttackEvidence("unavailable")
            samples = array("h")
            samples.frombytes(raw)
            if sys.byteorder != "little":
                samples.byteswap()
            levels = [
                _rms_by_channel(
                    samples, j * segment_frames, segment_frames, channels
                )
                for j in range(window_segments)
            ]
            best_ratio = 0.0
            best = None
            for j in range(
                pre_segments, pre_segments + round(MAX_DELAY_SECONDS / SEGMENT_SECONDS) + 1
            ):
                before = sum(levels[j - 3:j]) / 3
                after = sum(levels[j:j + 3]) / 3
                if after < MIN_ATTACK_RMS or after - before < MIN_RMS_JUMP:
                    continue
                ratio = after / max(before, 1.0)
                if ratio < MIN_ATTACK_RATIO or ratio <= best_ratio:
                    continue
                best_ratio = ratio
                best = (j, before, after)
            if best is None:
                return BassAttackEvidence("no_attack")
            j, before, after = best
            confidence = max(0.0, min(1.0, 1 - 1 / best_ratio))
            return BassAttackEvidence(
                status="attack_detected",
                confidence=round(confidence, 6),
                measured_onset_delta_seconds=round(
                    (j - pre_segments) * segment_frames / rate, 6
                ),
                pre_attack_rms=round(before, 3),
                post_attack_rms=round(after, 3),
            )
    except (OSError, EOFError, OverflowError, ValueError, wave.Error):
        return BassAttackEvidence("unavailable")
