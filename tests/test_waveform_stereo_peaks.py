from __future__ import annotations

from array import array
from pathlib import Path
import wave

import pytest
from pydantic import ValidationError

from rocksmith_cdlc_generator.waveform_cache import (
    WaveformEnvelope,
    _read_pcm16_mono_peak_samples,
)


def _write_stereo_pcm16(path: Path, frames: list[tuple[int, int]], *, sample_rate: int = 1000) -> None:
    samples = array("h")
    for left, right in frames:
        samples.extend((left, right))
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(samples.tobytes())


def test_waveform_preserves_phase_opposed_stereo_energy(tmp_path: Path) -> None:
    audio = tmp_path / "phase-opposed.wav"
    # Signed averaging would turn every frame into zero. The display envelope must
    # instead retain the audible peak from either channel.
    _write_stereo_pcm16(
        audio,
        [(24000, -24000)] * 100,
    )

    envelope = _read_pcm16_mono_peak_samples(audio, target_buckets=100)

    assert envelope.channels == 2
    assert envelope.bucket_count == 100
    expected = 24000 / 32768.0
    assert envelope.maximums[0] == pytest.approx(expected)
    assert envelope.minimums[0] == pytest.approx(-expected)
    assert all(peak > 0.70 for peak in envelope.maximums)
    assert all(peak < -0.70 for peak in envelope.minimums)


def test_waveform_preserves_peak_present_in_only_one_channel(tmp_path: Path) -> None:
    audio = tmp_path / "one-sided.wav"
    _write_stereo_pcm16(audio, [(0, 30000)] * 100)

    envelope = _read_pcm16_mono_peak_samples(audio, target_buckets=100)

    assert envelope.maximums[0] == pytest.approx(30000 / 32768.0)
    assert envelope.minimums[0] == 0.0


def test_waveform_schema_v2_rejects_old_channel_averaged_cache() -> None:
    with pytest.raises(ValidationError):
        WaveformEnvelope.model_validate(
            {
                "schema_version": 1,
                "audio_sha256": "0" * 64,
                "sample_rate_hz": 44100,
                "channels": 2,
                "frames": 44100,
                "duration_seconds": 1.0,
                "bucket_frames": 441,
                "minimums": [0.0],
                "maximums": [0.0],
            }
        )
