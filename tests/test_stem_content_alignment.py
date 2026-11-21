"""Known-truth, local and copyright-free content-clock regression tests.

The synthetic corpus checks detection, never proves actual separator quality.
"""
from __future__ import annotations

from array import array
from pathlib import Path
import math
import sys
import wave

import pytest

from rocksmith_cdlc_generator.auto_cdlc_truth import generate_known_truth, verify_known_truth
from rocksmith_cdlc_generator.stem_content_alignment import audit_stem_content_alignment


def _write_wav(path: Path, signal: array, *, rate: int = 12000) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as output:
        output.setframerate(rate)
        output.setnchannels(1)
        output.setsampwidth(2)
        output.writeframes(signal.tobytes())
    return path


def _shift(signal: array, lag_samples: int) -> array:
    if lag_samples > 0:
        return array("h", [0]) * lag_samples + signal[:-lag_samples]
    if lag_samples < 0:
        return signal[-lag_samples:] + array("h", [0]) * (-lag_samples)
    return array("h", signal)


@pytest.fixture(scope="module")
def distinct_bass_song(tmp_path_factory):
    folder = tmp_path_factory.mktemp("stem-clock")
    rate, count = 12000, 12 * 12000
    bass = array("h", [0]) * count
    master = array("h", [0]) * count
    notes = [
        (0.8, .38, 95), (1.5, .28, 116), (2.42, .5, 147),
        (3.15, .41, 105), (4.12, .36, 135), (5., .45, 100),
        (5.81, .31, 130), (6.7, .43, 80), (7.52, .42, 95),
        (8.3, .36, 125), (9.12, .4, 115), (10., .42, 144),
        (10.72, .42, 100),
    ]
    for start, duration, frequency in notes:
        for pos in range(int(duration * rate)):
            frame = round(start * rate) + pos
            envelope = min(1, pos / (.004 * rate)) * max(0, 1 - pos / (duration * rate)) ** .6
            bass[frame] = int(7000 * envelope * (
                math.sin(2 * math.pi * frequency * pos / rate)
                + .1 * math.sin(4 * math.pi * frequency * pos / rate)
            ))
    master[:] = bass
    for start in (1.12, 2.78, 3.65, 4.81, 5.92, 7.25, 8.82, 9.5, 10.42):
        for pos in range(int(rate * .06)):
            frame = round(start * rate) + pos
            master[frame] += int(800 * math.sin(2 * math.pi * 1000 * pos / rate)
                                  * (1 - pos / (.06 * rate)) ** 1.2)
    return folder, _write_wav(folder / "master.wav", master), bass, rate


@pytest.mark.parametrize("lag", [0, 0.04, 0.2, -0.08])
def test_content_audit_detects_known_lag_and_does_not_rephase_notes(
    distinct_bass_song, lag
) -> None:
    folder, master, bass, rate = distinct_bass_song
    candidate = _write_wav(folder / f"lag{lag}.wav", _shift(bass, round(lag * rate)), rate=rate)
    result = audit_stem_content_alignment(master, candidate)
    assert result.status == ("aligned" if lag == 0 else "shifted")
    assert result.lag_seconds == pytest.approx(lag, abs=.012)
    assert len(result.anchor_lags_seconds) >= 2
    assert all(x > .72 for x in result.anchor_correlations)


def test_content_audit_refuses_silence_and_unrelated_tone(distinct_bass_song) -> None:
    folder, master, bass, rate = distinct_bass_song
    silence = _write_wav(folder / "silence.wav", array("h", [0]) * len(bass), rate=rate)
    unrelated = _write_wav(folder / "unrelated.wav", array("h", (
        round(650 * math.sin(2 * math.pi * 119 * i / rate))
        for i in range(len(bass))
    )), rate=rate)
    for path in (silence, unrelated):
        result = audit_stem_content_alignment(master, path)
        assert result.status in {"insufficient_signal", "ambiguous"}
        assert result.lag_seconds is None


def test_content_audit_refuses_pcm_geometry_and_short_audio(tmp_path: Path) -> None:
    src = _write_wav(tmp_path / "a.wav", array("h", [0]) * 1000)
    bad = _write_wav(tmp_path / "b.wav", array("h", [0]) * 1001)
    assert audit_stem_content_alignment(src, bad).status == "incompatible"
    assert audit_stem_content_alignment(src, src).status == "insufficient_signal"


def test_uses_existing_copyright_free_original_clock_fixture(tmp_path: Path) -> None:
    master, truth_path = generate_known_truth(tmp_path / "truth")
    verified, truth = verify_known_truth(truth_path.parent)
    assert verified == master
    assert truth["bass_notes"][0]["onset_seconds"] == pytest.approx(7.13)
    result = audit_stem_content_alignment(master, master)
    assert result.status == "aligned"
    # Content alignment is not proof of stem isolation: both inputs can be
    # identical full mixes, which must not be promoted as isolated Bass.
