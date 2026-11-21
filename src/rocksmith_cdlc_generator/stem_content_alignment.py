"""Read-only, bounded content-delay audit for separated instrument audio.

Matching WAV metadata and hashes do not prove that audible content is on the
original recording clock. A positive result is timing evidence only, NOT
proof of source separation, musical pitch accuracy, or gameplay correctness.
"""
from __future__ import annotations

from array import array
from dataclasses import dataclass, asdict
import json
import os
from math import exp, log1p, pi, sqrt
from pathlib import Path
import sys
import wave


AUDIT_VERSION = "low-energy-correlation-v1"


@dataclass(frozen=True)
class StemContentAlignment:
    status: str  # aligned / shifted / ambiguous / insufficient_signal / incompatible
    lag_seconds: float | None  # Positive => stem content later than master
    anchor_lags_seconds: tuple[float, ...]
    anchor_correlations: tuple[float, ...]
    evaluated_anchors: int
    reason: str


def _geometry(path: Path) -> tuple[int, int, int, int, str]:
    with wave.open(str(path), "rb") as audio:
        info = (audio.getframerate(), audio.getnchannels(), audio.getnframes(),
                audio.getsampwidth(), audio.getcomptype())
    if info[0] < 1000 or info[1] not in (1, 2) or info[2] < 1 or info[3] != 2 or info[4] != "NONE":
        raise ValueError("Content audit needs mono/stereo uncompressed 16-bit PCM")
    return info


def _low_frequency_energy(path: Path, begin_frame: int, end_frame: int, hop: int) -> list[float]:
    """Low-pass each channel separately; avoid opposite-phase stereo cancellation."""
    with wave.open(str(path), "rb") as audio:
        audio.setpos(begin_frame)
        rate, channels = audio.getframerate(), audio.getnchannels()
        samples = array("h")
        samples.frombytes(audio.readframes(end_frame - begin_frame))
    if sys.byteorder != "little":
        samples.byteswap()
    alpha = 1.0 - exp(-2.0 * pi * 270.0 / rate)
    state = [0.0] * channels
    smooth = [0.0] * channels
    energy = []
    squares = 0.0
    count = 0
    for pos in range(0, len(samples), channels):
        for ch in range(channels):
            state[ch] += alpha * (samples[pos + ch] - state[ch])
            smooth[ch] += alpha * (state[ch] - smooth[ch])
            squares += smooth[ch] * smooth[ch]
        count += 1
        if count == hop:
            energy.append(log1p(sqrt(squares / (count * channels))))
            squares = 0.0
            count = 0
    return energy


def _correlation(a: list[float], b: list[float]) -> float:
    count = len(a)
    if not count or count != len(b):
        return 0.0
    mean_a, mean_b = sum(a) / count, sum(b) / count
    power_a = sum((x - mean_a) ** 2 for x in a)
    power_b = sum((x - mean_b) ** 2 for x in b)
    if power_a <= 1e-8 or power_b <= 1e-8:
        return 0.0
    return sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b)) / sqrt(power_a * power_b)


def audit_stem_content_alignment(
    source_path: Path, stem_path: Path, *,
    max_lag_seconds: float = 0.25,
    hop_seconds: float = 0.01,
    anchor_seconds: float = 3.0,
) -> StemContentAlignment:
    """Detect reproducible nonzero delays from independent audio landmarks.

    Requires 2+ agreeing signal windows and a unique correlation maximum.
    An unavailable/uncertain result fails closed. Does not move the score,
    playback clock, stems, or the original audio.
    """
    if not 0.03 <= max_lag_seconds <= 0.5 or not 0.005 <= hop_seconds <= 0.02:
        raise ValueError("Invalid bounded lag search")
    if not 1.0 <= anchor_seconds <= 8.0:
        raise ValueError("Invalid bounded anchor length")
    try:
        source, stem = _geometry(Path(source_path)), _geometry(Path(stem_path))
    except (OSError, EOFError, ValueError, wave.Error) as exc:
        return StemContentAlignment("incompatible", None, (), (), 0,
                                    f"Unreadable PCM: {type(exc).__name__}")
    if source != stem:
        return StemContentAlignment("incompatible", None, (), (), 0, "PCM geometry differs")
    rate, _channels, frames, _width, _type = source
    hop = max(1, round(rate * hop_seconds))
    lag_steps = round(max_lag_seconds * rate / hop)
    span = round(anchor_seconds * rate / hop)
    total = frames // hop
    if total < span + 2 * lag_steps + 20:
        return StemContentAlignment("insufficient_signal", None, (), (), 0,
                                    "Recording too short for independent content windows")
    margin = lag_steps + 3
    first, last = margin, total - margin - span
    anchors = tuple(dict.fromkeys((first, (first + last) // 2, last)))
    if len(anchors) < 2:
        return StemContentAlignment("insufficient_signal", None, (), (), 0,
                                    "Insufficient independent anchor windows")
    lags: list[float] = []
    correlations: list[float] = []
    independent_positions: list[int] = []
    for position in anchors:
        if any(abs(position - chosen) < span for chosen in independent_positions):
            # Overlapping windows cannot be counted as independent witnesses.
            continue
        begin, end = position - margin, position + span + margin
        mix = _low_frequency_energy(Path(source_path), begin * hop, end * hop, hop)
        isolated = _low_frequency_energy(Path(stem_path), begin * hop, end * hop, hop)
        x = mix[margin:margin + span]
        if (len(x) < span or len(isolated) < margin + span + lag_steps
                or max(x) - min(x) < 0.35):
            continue
        scores = [
            (shift, _correlation(x, isolated[margin + shift:margin + shift + span]))
            for shift in range(-lag_steps, lag_steps + 1)
        ]
        best_shift, highest = max(scores, key=lambda entry: entry[1])
        runners_up = [value for shift, value in scores if abs(shift - best_shift) >= 3]
        if highest < 0.72 or highest - max(runners_up, default=-1.0) < 0.045:
            continue
        independent_positions.append(position)
        lags.append(best_shift * hop / rate)
        correlations.append(highest)
    if len(lags) < 2:
        return StemContentAlignment("insufficient_signal" if not lags else "ambiguous",
                                    None, tuple(lags), tuple(correlations), len(anchors),
                                    "Fewer than two reliable independent timing anchors")
    if max(lags) - min(lags) > max(0.025, 2.5 * hop / rate):
        return StemContentAlignment("ambiguous", None, tuple(lags), tuple(correlations), len(anchors),
                                    "Content-delay estimates disagree across windows")
    lag = sorted(lags)[len(lags) // 2]
    if abs(lag) <= max(0.015, 1.5 * hop / rate):
        return StemContentAlignment("aligned", lag, tuple(lags), tuple(correlations), len(anchors),
                                    "Multiple independent low-frequency windows agree near zero")
    return StemContentAlignment("shifted", lag, tuple(lags), tuple(correlations), len(anchors),
                                "Detected content delay; do not shift the recording clock")


def write_project_bass_stem_clock_audit(project_dir: Path) -> Path:
    """Save privacy-safe local evidence, current only for the two input hashes.

    Recompute on every invocation; never trust or reuse an older JSON PASS
    merely because it has the same filename. No audio bytes, input filenames,
    or private song metadata are exported from this helper.
    """
    from .hashing import sha256_file
    from .stems import StemSeparationError, verified_project_stem

    project = Path(project_dir).resolve()
    master = (project / "audio" / "normalized.wav").resolve()
    result = StemContentAlignment("incompatible", None, (), (), 0, "No verified local Bass stem")
    master_hash = None
    stem_hash = None
    try:
        stem = verified_project_stem(project, "bass")
        master_hash, stem_hash = sha256_file(master), sha256_file(stem)
        result = audit_stem_content_alignment(master, stem)
        if sha256_file(master) != master_hash or sha256_file(stem) != stem_hash:
            result = StemContentAlignment("incompatible", None, (), (), 0,
                                          "Audio changed while measuring content delay")
    except (StemSeparationError, OSError, ValueError, wave.Error, EOFError):
        # No private media paths/errors in the recorded diagnostics.
        result = StemContentAlignment("incompatible", None, (), (), 0,
                                      "Missing or unverified source/stem")
        master_hash, stem_hash = None, None
    payload = {
        "schema_version": 1,
        "algorithm": AUDIT_VERSION,
        "recording_sha256": master_hash,
        "stem_sha256": stem_hash,
        **asdict(result),
        "authority": "read_only_content_timing_diagnostic_not_pitch_or_separation_proof",
    }
    target = (project / "analysis" / "bass_stem_content_alignment.json").resolve()
    if not target.is_relative_to(project):
        raise ValueError("Bass stem clock report must stay inside the private project")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, target)
    return target
