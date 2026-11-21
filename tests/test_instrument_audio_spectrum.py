from __future__ import annotations

from array import array
import math
from pathlib import Path
import wave

import pytest

from rocksmith_cdlc_generator.instrument_audio_spectrum import measure_spectrum


def _test_wav(path: Path, *, stereo: bool = False, frequency: float = 220.0) -> None:
    rate = 12000
    with wave.open(str(path), "wb") as out:
        out.setnchannels(2 if stereo else 1)
        out.setsampwidth(2)
        out.setframerate(rate)
        values = array("h")
        for i in range(rate):
            sample = round(10000 * math.sin(2 * math.pi * frequency * i / rate))
            if stereo:
                values.extend((sample, -sample))
            else:
                values.append(sample)
        out.writeframes(values.tobytes())


def test_spectrum_shows_measured_peak_in_selected_note_range(tmp_path: Path) -> None:
    source = tmp_path / "tone.wav"
    _test_wav(source)
    data = measure_spectrum(source, 0.3)
    peak = data.relative_magnitudes.index(max(data.relative_magnitudes))
    # Log grid is coarse; nearest bins cluster around the actual 220 Hz.
    assert 175 < data.frequencies_hz[peak] < 265
    assert len(data.frequencies_hz) == 36
    assert max(data.relative_magnitudes) == pytest.approx(1.0)
    assert data.center_seconds == pytest.approx(0.3)


def test_stereo_opposite_phase_does_not_cancel_into_false_silence(tmp_path: Path) -> None:
    source = tmp_path / "opposed.wav"
    _test_wav(source, stereo=True)
    data = measure_spectrum(source, 0.5)
    peak = data.relative_magnitudes.index(max(data.relative_magnitudes))
    assert 175 < data.frequencies_hz[peak] < 265
    assert max(data.relative_magnitudes) == 1.0


def test_spectral_invalid_grid_fails_closed(tmp_path: Path) -> None:
    source = tmp_path / "tone.wav"
    _test_wav(source)
    with pytest.raises(ValueError, match="Nyquist"):
        measure_spectrum(source, 0.5, maximum_hz=7000)
    with pytest.raises(ValueError, match="nonnegative"):
        measure_spectrum(source, -1)
