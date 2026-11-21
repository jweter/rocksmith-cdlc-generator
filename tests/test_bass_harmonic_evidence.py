"""Synthetic Bass harmonic cases: diagnostic evidence, never auto-trust."""
from __future__ import annotations

from array import array
import math
from pathlib import Path
import wave

import pytest

from rocksmith_cdlc_generator.bass_harmonic_evidence import measure_bass_harmonic_pattern
from rocksmith_cdlc_generator.instrument_audio_focus import midi_frequency


E1 = midi_frequency(28)
F1 = midi_frequency(29)
BASS_STANDARD = (28, 33, 38, 43)


def _wave(path: Path, components: list[tuple[float, float]], *, seconds: float = 3.0,
          stereo_opposite: bool = False) -> Path:
    rate = 8000
    n = round(rate * seconds)
    samples = array("h")
    for i in range(n):
        t = i / rate
        value = round(sum(amp * math.sin(2*math.pi*freq*t) for freq,amp in components))
        samples.append(value)
        if stereo_opposite:
            samples.append(-value)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as out:
        out.setnchannels(2 if stereo_opposite else 1)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes(samples.tobytes())
    return path


def _result(path: Path, midi: int = 28, *, tuning=BASS_STANDARD, duration=2.6):
    return measure_bass_harmonic_pattern(
        path, expected_midi=midi, tuning_midi=tuning,
        note_start_seconds=.10, note_duration_seconds=duration,
    )


def _partials(f: float) -> list[tuple[float,float]]:
    return [(f,6200),(2*f,3300),(3*f,1600),(4*f,700)]


def test_expected_e1_harmonics_beat_neighbor_and_octave(tmp_path: Path):
    path = _wave(tmp_path / "e1.wav", _partials(E1))
    result = _result(path)
    assert result.status == "plausible_pattern"
    assert result.observed_windows == 2
    assert result.minimum_candidate_margin >= 1.75
    assert result.candidate_fundamental_hz == pytest.approx(E1, abs=.001)
    assert result.source_sha256 is not None and len(result.source_sha256) == 64
    assert not result.note_pitch_verified
    assert not result.source_isolation_proven
    assert not result.score_authority_changed


def test_expected_f1_supported_but_neighbor_e1_is_not(tmp_path: Path):
    path = _wave(tmp_path / "f1.wav", _partials(F1))
    assert _result(path, 29).status == "plausible_pattern"
    assert _result(path, 28).status == "ambiguous"


def test_octave_only_tone_cannot_claim_missing_e1_fundamental(tmp_path: Path):
    path = _wave(tmp_path / "octave.wav", _partials(2*E1))
    assert _result(path, 28).status == "ambiguous"


def test_simultaneous_two_bass_pitches_refuse_single_note_authority(tmp_path: Path):
    path = _wave(tmp_path / "dual.wav", [
        (E1,4800),(2*E1,2400),(F1,4800),(2*F1,2400),
    ])
    assert _result(path, 28).status == "ambiguous"
    assert _result(path, 29).status == "ambiguous"


def test_silence_is_insufficient_and_short_percussion_does_not_promote(tmp_path: Path):
    quiet = _wave(tmp_path / "quiet.wav", [])
    assert _result(quiet).status == "insufficient_signal"
    attack = tmp_path / "kick.wav"
    rate = 8000
    samples = array("h", [0]) * (rate*3)
    for i in range(int(.065*rate)):
        t = i/rate
        samples[round(.35*rate)+i] = round(9000*math.sin(2*math.pi*80*t)*math.exp(-35*t))
    with wave.open(str(attack), "wb") as out:
        out.setnchannels(1);out.setsampwidth(2);out.setframerate(rate)
        out.writeframes(samples.tobytes())
    # A transient first window may be energetic but non-harmonic; the
    # diagnostic can reject it as ambiguous before reaching the silent
    # second window. Both outcomes must remain explicitly unqualified.
    rejected = _result(attack)
    assert rejected.status in {"ambiguous", "insufficient_signal"}
    assert rejected.note_pitch_verified is False
    assert rejected.score_authority_changed is False


def test_stereo_phase_reversal_does_not_cancel_detected_pattern(tmp_path: Path):
    path = _wave(tmp_path / "phase.wav", _partials(E1), stereo_opposite=True)
    assert _result(path).status == "plausible_pattern"


def test_missing_or_wrong_tuning_and_short_note_do_not_guess(tmp_path: Path):
    path = _wave(tmp_path / "song.wav", _partials(E1))
    assert _result(path, tuning=None).status == "unplayable"
    assert _result(path, tuning=(20, 25, 30, 35), midi=60).status == "unplayable"
    assert _result(path, duration=.55).status == "insufficient_signal"


def test_corrupt_pcm_payload_is_never_claimed(tmp_path: Path):
    path = _wave(tmp_path / "source.wav", _partials(E1))
    path.write_bytes(path.read_bytes()[:-2])
    assert _result(path).status == "unavailable"


@pytest.mark.parametrize("time,duration", [(-1,2),(0,0),(float("inf"),2),(.1,float("nan"))])
def test_invalid_time_arguments_fail_closed(tmp_path: Path, time, duration):
    path = _wave(tmp_path / "source.wav", _partials(E1))
    with pytest.raises(ValueError):
        measure_bass_harmonic_pattern(
            path, expected_midi=28, tuning_midi=BASS_STANDARD,
            note_start_seconds=time, note_duration_seconds=duration,
        )
