"""Deterministic, non-authoritative instrument-register listening previews.

Focused audio is NOT an isolated instrument stem and never licenses note promotion.
The original normalized recording remains the one recording-time authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import wave


FOCUS_VERSION = "iir-register-v1"


class FocusUnavailable(RuntimeError):
    """Focused listening cannot be prepared safely."""


@dataclass(frozen=True)
class InstrumentFocusProfile:
    role: str
    tuning_midi: tuple[int, ...]
    low_hz: float
    high_hz: float
    highest_fret: int
    harmonic_count: int

    def as_dict(self) -> dict:
        return {
            "role": self.role,
            "tuning_midi": list(self.tuning_midi),
            "low_hz": self.low_hz,
            "high_hz": self.high_hz,
            "highest_fret": self.highest_fret,
            "harmonic_count": self.harmonic_count,
        }


def midi_frequency(midi: int) -> float:
    if not isinstance(midi, int) or isinstance(midi, bool) or not 0 <= midi <= 127:
        raise ValueError("MIDI pitch must be an integer in 0..127")
    return 440.0 * (2.0 ** ((midi - 69) / 12.0))


def focus_profile(
    role: str, tuning_midi: list[int] | tuple[int, ...] | None, *, highest_fret: int = 24
) -> InstrumentFocusProfile:
    if role not in {"bass", "lead", "rhythm"}:
        raise ValueError("Focused audio needs an explicit Bass, Lead, or Rhythm role")
    if tuning_midi is None:
        raise FocusUnavailable("Confirmed instrument tuning is required for frequency-focused audio")
    tuning = tuple(tuning_midi)
    if role == "bass" and not 4 <= len(tuning) <= 6:
        raise ValueError("Bass tuning must have 4–6 strings")
    if role != "bass" and not 6 <= len(tuning) <= 8:
        raise ValueError("Guitar tuning must have 6–8 strings")
    if not isinstance(highest_fret, int) or isinstance(highest_fret, bool) or not 0 <= highest_fret <= 30:
        raise ValueError("highest_fret must be between 0 and 30")
    for pitch in tuning:
        midi_frequency(pitch)
    # Mild second-order high-pass, safely below the lowest open-string F0.
    low_hz = max(10.0, midi_frequency(min(tuning)) * 0.5)
    # Keep several harmonics of notes at the high end of the playable register.
    # This is listening EQ, not evidence that another instrument was removed.
    harmonic_count = 3 if role == "bass" else 2
    high_pitch = min(127, max(tuning) + highest_fret)
    high_hz = min(6500.0, max(230.0, midi_frequency(high_pitch) * harmonic_count))
    if low_hz >= high_hz:
        raise FocusUnavailable("The tuning produces an invalid instrument-focused passband")
    return InstrumentFocusProfile(
        role, tuning, round(low_hz, 3), round(high_hz, 3), highest_fret, harmonic_count
    )


def candidate_positions(
    midi: int, tuning_midi: list[int] | tuple[int, ...], *, highest_fret: int = 24
) -> tuple[tuple[int, int], ...]:
    """Return (zero-based string, fret) without guessing physical position."""
    midi_frequency(midi)
    if highest_fret < 0 or highest_fret > 30:
        raise ValueError("highest_fret must be in 0..30")
    return tuple(
        (string, midi - open_pitch)
        for string, open_pitch in enumerate(tuning_midi)
        if 0 <= midi - open_pitch <= highest_fret
    )


def _hash(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _wave_geometry(path: Path) -> tuple[int, int, int, int]:
    with wave.open(str(path), "rb") as source:
        if source.getsampwidth() != 2 or source.getcomptype() != "NONE":
            raise FocusUnavailable("Focused preview requires uncompressed 16-bit PCM WAV")
        geometry = (
            source.getframerate(),
            source.getnchannels(),
            source.getnframes(),
            source.getsampwidth(),
        )
    if geometry[0] <= 0 or geometry[1] not in (1, 2) or geometry[2] <= 0:
        raise FocusUnavailable("Invalid input audio geometry")
    return geometry


def prepare_focused_audio(
    project_dir: Path,
    role: str,
    tuning_midi: list[int] | tuple[int, ...] | None,
    *,
    highest_fret: int = 24,
) -> Path:
    """Render a private, cached frequency-focused WAV; never touch the master.

    Synchronous for test/worker use: GUI callers must call on a background thread.
    Only a byte-for-byte sample geometry match may become a preview source.
    """
    project = Path(project_dir).resolve()
    source = project / "audio" / "normalized.wav"
    if not source.is_file():
        raise FocusUnavailable("Normalize the original project audio before preparing focus")
    profile = focus_profile(role, tuning_midi, highest_fret=highest_fret)
    geometry = _wave_geometry(source)
    sample_rate = geometry[0]
    if profile.high_hz >= sample_rate * 0.45:
        raise FocusUnavailable("Sample rate is too low for this tuning's focused preview")
    source_hash = _hash(source)
    parameters = {"version": FOCUS_VERSION, "source_sha256": source_hash, "sample_rate": sample_rate, **profile.as_dict()}
    cache_key = sha256(json.dumps(parameters, sort_keys=True).encode("utf-8")).hexdigest()
    folder = project / "audio" / "derived" / "instrument_focus"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{cache_key}.wav"
    receipt = folder / f"{cache_key}.json"
    if target.is_file() and receipt.is_file():
        try:
            stored = json.loads(receipt.read_text(encoding="utf-8"))
            if (
                stored.get("parameters") == parameters
                and stored.get("output_sha256") == _hash(target)
                and _wave_geometry(target) == geometry
            ):
                return target
        except (OSError, ValueError, KeyError, json.JSONDecodeError, wave.Error, FocusUnavailable):
            pass

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise FocusUnavailable("FFmpeg is required to prepare an instrument-focused listening preview")
    fd, staging_name = tempfile.mkstemp(prefix="focused-", suffix=".wav", dir=folder)
    os.close(fd)
    staging = Path(staging_name)
    meta_staging = staging.with_suffix(".json")
    try:
        command = [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
            "-i", str(source), "-map", "0:a:0", "-vn",
            "-af", f"highpass=f={profile.low_hz:.3f},lowpass=f={profile.high_hz:.3f}",
            "-c:a", "pcm_s16le", str(staging),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, timeout=180)
        if completed.returncode != 0:
            raise FocusUnavailable("Frequency-focused FFmpeg render failed: " + (completed.stderr.strip() or str(completed.returncode))[:280])
        if _wave_geometry(staging) != geometry:
            raise FocusUnavailable("Focused audio changed channel/sample geometry; it cannot use the shared recording clock")
        output_hash = _hash(staging)
        meta_staging.write_text(
            json.dumps({"parameters": parameters, "output_sha256": output_hash}, sort_keys=True, indent=2),
            encoding="utf-8",
        )
        os.replace(staging, target)
        os.replace(meta_staging, receipt)
        return target
    finally:
        staging.unlink(missing_ok=True)
        meta_staging.unlink(missing_ok=True)
