"""Deterministic, copyright-free audio with cryptographically checked known timing.

This is an external audio-clock truth fixture: the test knows the precise
samples where notes and beats were synthesized before either analysis engine
runs. Unlike comparing two transcribers, agreement cannot hide a shared
global offset. This does NOT measure accuracy of real commercial songs.
"""
from __future__ import annotations

from array import array
from dataclasses import asdict
from hashlib import sha256
from io import BytesIO
import json
from math import pi, sin
from pathlib import Path
import sys
import wave

from .corpus_differential_harness import refuse_output_inside_repository_checkout

PROFILE = "two-bar-phase-sentinel-v1"
SAMPLE_RATE = 44100
BPM = 120
BEAT_COUNT = 40
FIRST_BEAT_FRAME = round(7.13 * SAMPLE_RATE)
FRAMES_PER_BEAT = SAMPLE_RATE // 2
PITCHES = (40, 43, 45, 47, 48, 50, 52, 55)
SILENT_BEATS = frozenset((16, 17, 18, 19))


class KnownTruthError(ValueError):
    """Missing, modified or invalid synthetic fixture evidence."""


def _canonical_events() -> tuple[list[int], list[dict[str, object]]]:
    beat_frames = [FIRST_BEAT_FRAME + i * FRAMES_PER_BEAT for i in range(BEAT_COUNT)]
    notes = []
    for i, frame in enumerate(beat_frames):
        if i in SILENT_BEATS:
            continue
        duration_frames = round((0.26 if i % 3 else 0.34) * SAMPLE_RATE)
        notes.append({
            "onset_seconds": frame / SAMPLE_RATE,
            "duration_seconds": duration_frames / SAMPLE_RATE,
            "midi": PITCHES[i % len(PITCHES)],
        })
    return beat_frames, notes


def _render_wav() -> bytes:
    """Pure-stdlib waveform with discrete sample positions as the source of truth.

    A distinct percussion tick persists through the Bass silence, allowing
    beat and post-silence reacquisition to be evaluated separately. All
    samples are synthesized from the canonical grid, not from predictions.
    """
    beat_frames, notes = _canonical_events()
    frame_count = beat_frames[-1] + 2 * SAMPLE_RATE
    samples = array("h", [0]) * frame_count

    for i, frame in enumerate(beat_frames):
        frequency = 1750 if i % 4 == 0 else 1150
        amplitude = 7000 if i % 4 == 0 else 4300
        length = round(0.025 * SAMPLE_RATE)
        for pos in range(length):
            envelope = (1 - pos / length) ** 3
            value = int(amplitude * envelope * sin(2 * pi * frequency * pos / SAMPLE_RATE))
            samples[frame + pos] += value

    for note in notes:
        start = round(float(note["onset_seconds"]) * SAMPLE_RATE)
        length = round(float(note["duration_seconds"]) * SAMPLE_RATE)
        frequency = 440 * 2 ** ((int(note["midi"]) - 69) / 12)
        for pos in range(length):
            envelope = min(1.0, pos / (0.006 * SAMPLE_RATE)) * (1 - pos / length) ** 1.2
            phase = 2 * pi * frequency * pos / SAMPLE_RATE
            value = int(3300 * envelope * (sin(phase) + 0.25 * sin(2 * phase)))
            samples[start + pos] += value

    if sys.byteorder != "little":
        samples.byteswap()
    handle = BytesIO()
    with wave.open(handle, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(samples.tobytes())
    return handle.getvalue()


def canonical_truth(wav_sha256: str) -> dict[str, object]:
    beat_frames, notes = _canonical_events()
    return {
        "schema_version": 1,
        "profile": PROFILE,
        "provenance": "reproducible_original_synthesis",
        "source_audio_sha256": wav_sha256,
        "sample_rate_hz": SAMPLE_RATE,
        "duration_seconds": (beat_frames[-1] + 2 * SAMPLE_RATE) / SAMPLE_RATE,
        "bpm": BPM,
        "time_signature": "4/4",
        "beats_seconds": [x / SAMPLE_RATE for x in beat_frames],
        "downbeats_seconds": [x / SAMPLE_RATE for i, x in enumerate(beat_frames) if i % 4 == 0],
        "bass_notes": notes,
    }


def generate_known_truth(destination: Path) -> tuple[Path, Path]:
    """Create or verify identical fixture files, never replace unrelated data."""
    destination = destination.expanduser().resolve()
    refuse_output_inside_repository_checkout(destination / "fixture.json")
    wav_content = _render_wav()
    wav_sha = sha256(wav_content).hexdigest()
    metadata = json.dumps(canonical_truth(wav_sha), indent=2, sort_keys=True) + "\n"
    wav_path = destination / "original_synthetic.wav"
    truth_path = destination / "fixture.json"
    if wav_path.exists() and wav_path.read_bytes() != wav_content:
        raise KnownTruthError("Refusing to overwrite unrelated synthetic audio")
    if truth_path.exists() and truth_path.read_text(encoding="utf-8") != metadata:
        raise KnownTruthError("Refusing to overwrite unrelated truth metadata")
    destination.mkdir(parents=True, exist_ok=True)
    if not wav_path.exists():
        wav_path.write_bytes(wav_content)
    if not truth_path.exists():
        truth_path.write_text(metadata, encoding="utf-8")
    return wav_path, truth_path


def verify_known_truth(directory: Path) -> tuple[Path, dict[str, object]]:
    """Regenerate audio AND event metadata; reject forged/edited truth files."""
    directory = directory.expanduser().resolve()
    wav_path = directory / "original_synthetic.wav"
    truth_path = directory / "fixture.json"
    if not wav_path.is_file() or not truth_path.is_file():
        raise KnownTruthError("Expected fixture.json and original_synthetic.wav")
    try:
        raw = json.loads(truth_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise KnownTruthError("Invalid truth JSON") from exc
    expected_wav = _render_wav()
    expected = canonical_truth(sha256(expected_wav).hexdigest())
    if raw != expected:
        raise KnownTruthError("Known-truth metadata differs from reproducible fixture specification")
    if wav_path.stat().st_size != len(expected_wav) or sha256(wav_path.read_bytes()).hexdigest() != expected["source_audio_sha256"]:
        raise KnownTruthError("Audio bytes differ from reproducible known-truth waveform")
    return wav_path, expected
