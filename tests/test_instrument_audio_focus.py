from __future__ import annotations

from array import array
import math
from pathlib import Path
import shutil
import wave

import pytest

from rocksmith_cdlc_generator.instrument_audio_focus import (
    FocusUnavailable,
    candidate_positions,
    focus_profile,
    midi_frequency,
    prepare_focused_audio,
)


def _write_test_source(path: Path, *, sample_rate: int = 44100) -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = array("h", (
        int(4500 * math.sin(2 * math.pi * 55 * i / sample_rate)
            + 4500 * math.sin(2 * math.pi * 6000 * i / sample_rate))
        for i in range(sample_rate)
    ))
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(data.tobytes())
    return path.read_bytes()


def _projection(path: Path, frequency: float) -> float:
    with wave.open(str(path), "rb") as stream:
        rate = stream.getframerate()
        samples = array("h")
        samples.frombytes(stream.readframes(stream.getnframes()))
    # Skip leading filter transient. This is an independent synchronous pitch-energy oracle.
    values = samples[rate // 5 :]
    sin_sum = sum(x * math.sin(2 * math.pi * frequency * (i + rate // 5) / rate) for i, x in enumerate(values))
    cos_sum = sum(x * math.cos(2 * math.pi * frequency * (i + rate // 5) / rate) for i, x in enumerate(values))
    return 2.0 * math.hypot(sin_sum, cos_sum) / len(values)


def test_pitch_frequency_and_tuning_constrained_positions() -> None:
    assert midi_frequency(28) == pytest.approx(41.2034, rel=1e-4)
    assert midi_frequency(40) == pytest.approx(82.4069, rel=1e-4)
    assert candidate_positions(40, (28, 33, 38, 43)) == ((0, 12), (1, 7), (2, 2))
    assert candidate_positions(23, (28, 33, 38, 43)) == ()
    with pytest.raises(ValueError):
        midi_frequency(True)


def test_focus_profile_uses_confirmed_role_tuning_and_harmonics() -> None:
    bass = focus_profile("bass", (28, 33, 38, 43))
    guitar = focus_profile("lead", (40, 45, 50, 55, 59, 64))
    drop_d = focus_profile("rhythm", (38, 45, 50, 55, 59, 64))
    low_b = focus_profile("bass", (23, 28, 33, 38, 43))
    assert bass.low_hz < midi_frequency(28)
    assert low_b.low_hz < bass.low_hz
    assert drop_d.low_hz < guitar.low_hz
    assert bass.high_hz < guitar.high_hz
    assert bass.harmonic_count == 3
    with pytest.raises(FocusUnavailable, match="Confirmed instrument tuning"):
        focus_profile("bass", None)
    with pytest.raises(ValueError, match="Bass tuning"):
        focus_profile("bass", (28, 33))
    with pytest.raises(ValueError, match="role"):
        focus_profile("drums", (28, 33, 38, 43))


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="FFmpeg not present in the CI job")
def test_focus_renders_cached_sample_aligned_audio_without_mutating_master(tmp_path: Path) -> None:
    master = tmp_path / "audio" / "normalized.wav"
    original_bytes = _write_test_source(master)
    output = prepare_focused_audio(tmp_path, "bass", (28, 33, 38, 43))
    assert output.exists() and output != master
    assert master.read_bytes() == original_bytes
    with wave.open(str(master), "rb") as src, wave.open(str(output), "rb") as rendered:
        assert (src.getnframes(), src.getframerate(), src.getnchannels(), src.getsampwidth()) == (
            rendered.getnframes(), rendered.getframerate(), rendered.getnchannels(), rendered.getsampwidth()
        )
    assert _projection(output, 55) > _projection(master, 55) * 0.55
    assert _projection(output, 6000) < _projection(master, 6000) * 0.08
    assert prepare_focused_audio(tmp_path, "bass", (28, 33, 38, 43)) == output
    assert prepare_focused_audio(tmp_path, "bass", (23, 28, 33, 38, 43)) != output
    assert master.read_bytes() == original_bytes


def test_focus_fails_closed_when_audio_or_tuning_missing(tmp_path: Path) -> None:
    with pytest.raises(FocusUnavailable, match="Normalize"):
        prepare_focused_audio(tmp_path, "bass", (28, 33, 38, 43))
    _write_test_source(tmp_path / "audio" / "normalized.wav")
    with pytest.raises(FocusUnavailable, match="Confirmed instrument tuning"):
        prepare_focused_audio(tmp_path, "bass", None)
