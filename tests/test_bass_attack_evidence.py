"""Canonical #796 slice 32: independent PCM transient evidence for Bass events.

Every audio sample is original synthetic signal. No licensed song, model,
separator, OS audio device, private path, or human laptop test is used.
"""
from __future__ import annotations

from array import array
from dataclasses import asdict
import json
import math
from pathlib import Path
import sys
import wave

import pytest

from rocksmith_cdlc_generator.bass_attack_evidence import (
    BassAttackEvidence, inspect_bass_attack_onset,
)
from rocksmith_cdlc_generator.reconciliation import (
    CURRENT_RECONCILIATION_ALGORITHM_VERSION,
    reconcile_bass_sources, reconciled_bass_chart_is_current,
)
from rocksmith_cdlc_generator.source_import import SourceTrustClass
from tests.test_bass_octave_negative import _synthetic_score_alignment_and_note

RATE = 8000
START = .40
E1 = 41.2034446


def synth(path: Path, kind: str, *, stereo_opposite: bool = False) -> Path:
    out = array("h")
    for i in range(3 * RATE):
        t = i / RATE
        if kind == "silent":
            val = 0
        elif kind == "dc":
            val = 12000
        elif kind == "steady":
            val = round(6500 * math.sin(2 * math.pi * E1 * t))
        elif kind in ("onset", "late40", "late110", "stereo"):
            delay = {"onset": 0, "late40": .04, "late110": .11, "stereo": 0}[kind]
            start = START + delay
            val = (round(6500 * math.sin(2 * math.pi * E1 * (t - start)))
                   if t >= start else 0)
        elif kind == "impulse":
            val = (round(18000 * math.sin(2 * math.pi * 1300 * (t - START)))
                   if START <= t < START + .003 else 0)
        else:
            raise AssertionError(kind)
        if stereo_opposite:
            out.extend((val, -val))
        else:
            out.append(val)
    if sys.byteorder != "little":
        out.byteswap()
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as dst:
        dst.setnchannels(2 if stereo_opposite else 1)
        dst.setsampwidth(2)
        dst.setframerate(RATE)
        dst.writeframes(out.tobytes())
    return path


def screen(path: Path, *, start: float = START, duration: float = 1.5):
    return inspect_bass_attack_onset(
        path, note_start_seconds=start, note_duration_seconds=duration,
    )


@pytest.mark.parametrize("kind", ["onset", "late40"])
def test_measured_pcm_attack_qualifies_without_fundamental_or_pyin_estimate(kind, tmp_path):
    wav = synth(tmp_path / "attack.wav", kind)
    result = screen(wav)
    assert result.status == "attack_detected"
    assert result.independent_attack
    assert result.confidence >= .60
    assert result.measured_onset_delta_seconds is not None
    assert 0 <= result.measured_onset_delta_seconds <= .08
    assert result.post_attack_rms > result.pre_attack_rms
    assert not result.bass_pitch_verified
    assert not result.source_isolation_proven
    assert not result.recording_clock_verified
    assert not result.musical_pass_proven


@pytest.mark.parametrize("kind", ["silent", "dc", "steady", "late110", "impulse"])
def test_no_independent_onset_for_continuous_tone_dc_silence_late_or_click(kind, tmp_path):
    wav = synth(tmp_path / (kind + ".wav"), kind)
    result = screen(wav)
    assert result.status == "no_attack"
    assert not result.independent_attack
    assert result.confidence == 0.0
    assert result.measured_onset_delta_seconds is None


def test_stereo_polarity_cannot_cancel_real_attack(tmp_path):
    wav = synth(tmp_path / "inverse.wav", "stereo", stereo_opposite=True)
    assert screen(wav).independent_attack


def test_truncated_missing_and_unsupported_pcm_never_qualify(tmp_path):
    wav = synth(tmp_path / "corrupt.wav", "onset")
    wav.write_bytes(wav.read_bytes()[:-2])
    assert screen(wav).status == "unavailable"
    assert screen(tmp_path / "nonexistent.wav").status == "unavailable"
    good = synth(tmp_path / "short.wav", "onset")
    assert screen(good, start=.05).status == "insufficient_signal"
    assert screen(good, duration=.05).status == "insufficient_signal"


@pytest.mark.parametrize("invalid", [
    {"note_start_seconds": -1}, {"note_start_seconds": float("nan")},
    {"note_start_seconds": True}, {"note_start_seconds": float("inf")},
    {"note_duration_seconds": 0}, {"note_duration_seconds": float("nan")},
    {"note_duration_seconds": "fake"},
])
def test_invalid_timing_arguments_never_read_files(invalid, tmp_path):
    args = {"note_start_seconds": .4, "note_duration_seconds": 1.5}
    args.update(invalid)
    with pytest.raises(ValueError, match="INVALID_BASS_ATTACK_ONSET_ARGUMENT"):
        inspect_bass_attack_onset(tmp_path / "missing.wav", **args)


@pytest.mark.parametrize("kind,expected", [
    ("silent", "NO_INDEPENDENT_ATTACK"),
    ("dc", "NO_INDEPENDENT_ATTACK"),
    ("steady", "NO_INDEPENDENT_ATTACK"),
    ("late110", "NO_INDEPENDENT_ATTACK"),
    ("impulse", "NO_INDEPENDENT_ATTACK"),
    ("onset", "QUALIFIED"),
    ("late40", "QUALIFIED"),
])
def test_real_reconciliation_denies_fake_perfect_pyin_without_independent_pcm_attack(
    kind, expected, tmp_path,
):
    wav = synth(tmp_path / "synthetic-false-pyin.wav", kind)
    source, alignment, audio = _synthetic_score_alignment_and_note()
    chart, _ = reconcile_bass_sources(
        source, alignment, audio,
        # Synthetic test deliberately grants all *preceding* provenance,
        # pitch, confidence, and octave gates to isolate onset authority.
        verified_stem_provenance=True,
        octave_negative_probe=lambda *_: "not_detected",
        attack_onset_probe=lambda start, duration: screen(
            wav, start=start, duration=duration
        ),
    )
    note = chart.notes[0]
    assert note.qualification_reasons == [expected]
    assert note.review_required == (expected != "QUALIFIED")
    assert note.trust_class == (
        SourceTrustClass.symbolic_verified if expected == "QUALIFIED"
        else SourceTrustClass.symbolic_unverified
    )
    assert note.qualification_observations["independent_attack_detected"] == (
        expected == "QUALIFIED"
    )
    assert note.qualification_thresholds["minimum_independent_attack_confidence"] == .60
    assert note.qualification_thresholds["maximum_independent_attack_delay_seconds"] == .08
    assert str(wav) not in chart.model_dump_json()


def test_unavailable_and_short_local_attack_reading_fail_closed():
    source, alignment, audio = _synthetic_score_alignment_and_note()
    for status, reason in [
        ("unavailable", "ATTACK_SCREEN_UNAVAILABLE"),
        ("insufficient_signal", "INSUFFICIENT_ATTACK_EVIDENCE"),
    ]:
        chart, _ = reconcile_bass_sources(
            source, alignment, audio, verified_stem_provenance=True,
            octave_negative_probe=lambda *_: "not_detected",
            attack_onset_probe=lambda *_: BassAttackEvidence(status),
        )
        assert chart.notes[0].qualification_reasons == [reason]
        assert chart.notes[0].review_required
        assert chart.notes[0].trust_class != SourceTrustClass.symbolic_verified


def test_untrusted_source_or_octave_negative_skips_attack_probe():
    source, alignment, audio = _synthetic_score_alignment_and_note()
    def never(*_):
        raise AssertionError("No PCM attack probe for already rejected notes")
    for verified, octave, reason in [
        (False, "not_detected", "UNVERIFIED_STEM"),
        (True, "octave_leakage", "OCTAVE_LEAKAGE_NEGATIVE"),
    ]:
        chart, _ = reconcile_bass_sources(
            source, alignment, audio, verified_stem_provenance=verified,
            octave_negative_probe=lambda *_: octave,
            attack_onset_probe=never,
        )
        assert chart.notes[0].qualification_reasons == [reason]


def test_invalid_probe_types_or_evidence_do_not_silently_grant_authority():
    source, alignment, audio = _synthetic_score_alignment_and_note()
    with pytest.raises(ValueError, match="INVALID_BASS_ATTACK_ONSET_PROBE"):
        reconcile_bass_sources(
            source, alignment, audio,
            verified_stem_provenance=True, attack_onset_probe=True,
        )
    with pytest.raises(ValueError, match="INVALID_BASS_ATTACK_EVIDENCE"):
        reconcile_bass_sources(
            source, alignment, audio, verified_stem_provenance=True,
            attack_onset_probe=lambda *_: BassAttackEvidence("imagined_pass"),
        )


def test_old_v8_cached_symbolic_verified_notes_are_stale_under_attack_gate(tmp_path):
    assert CURRENT_RECONCILIATION_ALGORITHM_VERSION == 9
    source, alignment, audio = _synthetic_score_alignment_and_note()
    chart, _ = reconcile_bass_sources(
        source, alignment, audio, verified_stem_provenance=True,
    )
    payload = chart.model_dump(mode="json")
    payload["reconciliation_algorithm_version"] = 8
    old = tmp_path / "v8-unverified-attack.json"
    old.write_text(json.dumps(payload), encoding="utf-8")
    assert not reconciled_bass_chart_is_current(old)
    payload["reconciliation_algorithm_version"] = 9
    new = tmp_path / "v9-current.json"
    new.write_text(json.dumps(payload), encoding="utf-8")
    assert reconciled_bass_chart_is_current(new)


def test_attack_report_does_not_contain_private_path_or_claim_pitch_truth(tmp_path):
    wav = synth(tmp_path / "private-recording.wav", "onset")
    report = screen(wav)
    result = json.dumps(asdict(report))
    assert "private-recording.wav" not in result
    assert str(tmp_path) not in result
    assert report.bass_pitch_verified is False
    assert report.recording_clock_verified is False
    assert report.musical_pass_proven is False
