"""Canonical #796 slice 28: synthetic unrelated/percussion-only Bass negatives.

Only original synthesized PCM is used; the intentionally high-confidence
transcription is adversarial metadata, not a model inference result.
"""
from __future__ import annotations

from array import array
import math
from pathlib import Path
import sys
from types import SimpleNamespace
import wave

import pytest

from rocksmith_cdlc_generator.bass_negative_signal import (
    screen_bass_stem_obvious_negatives,
)
from rocksmith_cdlc_generator.hashing import sha256_file
from rocksmith_cdlc_generator.reconciliation import (
    _note_qualification, is_verified_bass_stem_transcription,
)
from rocksmith_cdlc_generator.transcription import BassTranscription, NoteEvent


RATE = 8000
SECONDS = 3.0


def _samples(kind: str) -> array:
    pcm = array("h")
    for i in range(int(RATE * SECONDS)):
        t = i / RATE
        if kind in {"silence", "dc"}:
            value = 0 if kind == "silence" else 12000
        elif kind in {"kick", "unrelated_drum", "dense_kick"}:
            period = 0.50 if kind != "dense_kick" else 0.36
            local = (t + 0.20) % period
            if local < 0.055:
                # Separate attacks with short decays; no Bass sustain.
                source = 62.0 if kind != "unrelated_drum" else 890.0
                value = round(9500 * math.sin(2*math.pi*source*local)
                              * math.exp(-33*local))
            else:
                value = 0
        elif kind == "bass":
            value = round(
                6000 * math.sin(2*math.pi*41.2034446*t) +
                2800 * math.sin(2*math.pi*82.4068892*t)
            )
        else:
            raise AssertionError("Unknown synthetic generator")
        pcm.append(value)
    if sys.byteorder != "little":
        pcm.byteswap()
    return pcm


def _wav(path: Path, kind: str, *, inverted_stereo: bool = False) -> Path:
    samples = _samples(kind)
    if inverted_stereo:
        stereo = array("h")
        for val in samples:
            stereo.extend((val, -val))
        samples = stereo
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as out:
        out.setnchannels(2 if inverted_stereo else 1)
        out.setsampwidth(2)
        out.setframerate(RATE)
        out.writeframes(samples.tobytes())
    return path


@pytest.mark.parametrize("kind,expected", [
    ("silence", "silence_only"),
    ("dc", "silence_only"),
    ("kick", "transient_only"),
    ("unrelated_drum", "transient_only"),
    ("dense_kick", "transient_only"),
    ("bass", "not_obviously_negative"),
])
def test_synthetic_silence_drums_unrelated_pulses_never_become_bass(kind, expected, tmp_path):
    source = _wav(tmp_path / f"{kind}.wav", kind)
    result = screen_bass_stem_obvious_negatives(source)
    assert result.status == expected
    assert result.inspected_windows > 0
    assert result.not_obviously_negative == (kind == "bass")
    assert not result.source_isolation_proven
    assert not result.bass_instrument_proven
    assert not result.note_pitch_verified
    assert not result.musical_pass_proven


def test_stereo_phase_reversal_does_not_make_real_sustained_tone_look_silent(tmp_path):
    source = _wav(tmp_path / "stereo.wav", "bass", inverted_stereo=True)
    assert screen_bass_stem_obvious_negatives(source).not_obviously_negative


@pytest.mark.parametrize("kind", ["silence", "kick", "unrelated_drum", "dense_kick"])
def test_percussion_only_fails_actual_trusted_stem_gate_even_with_fake_perfect_pyin(
    tmp_path, monkeypatch, kind,
):
    """Force the earlier gates green; the new negative control must still veto."""
    project = tmp_path / "song"
    master = _wav(project / "audio" / "normalized.wav", "bass")
    stem = _wav(project / "stems" / "bass.wav", kind)
    assert sha256_file(master) != sha256_file(stem)

    from rocksmith_cdlc_generator import reconciliation as rec
    monkeypatch.setattr(rec, "verified_project_stem", lambda *_: stem.resolve())
    monkeypatch.setattr(
        rec, "audit_stem_content_alignment",
        lambda *_: SimpleNamespace(status="aligned"),
    )
    monkeypatch.setattr(
        rec, "screen_stem_nontrivial_difference",
        lambda *_: SimpleNamespace(status="nontrivial_difference"),
    )
    # Even fabricated 100% self-reported pYIN confidence and an accepted
    # stem filename/clock/hash must not qualify a drum/silent source.
    confident = NoteEvent(
        start=.5, duration=.8, midi=28, confidence=1.0,
        pitch_confidence=1.0, timing_confidence=1.0,
    )
    audio = BassTranscription(
        engine="synthetic-adversary-NOT-model-inference",
        source_path=str(stem), source_sha256=sha256_file(stem),
        sample_rate_hz=RATE, notes=[confident],
    )
    source_verified = is_verified_bass_stem_transcription(project, audio)
    assert source_verified is False
    reasons, observations, thresholds = _note_qualification(
        verified_stem=source_verified,
        onset_delta=0.0, audio_note=confident,
        region_confidence=1.0,
        verified_onset_tolerance_seconds=.08,
        minimum_audio_confidence=.70, minimum_pitch_confidence=.60,
        minimum_timing_confidence=.75, minimum_alignment_confidence=.70,
    )
    assert reasons == ["UNVERIFIED_STEM"]
    assert observations["verified_stem_provenance"] is False
    assert thresholds["maximum_verified_onset_delta_seconds"] == .08


def test_sustained_bass_only_passes_negative_screen_not_isolation_proof(tmp_path):
    stem = _wav(tmp_path / "bass.wav", "bass")
    screen = screen_bass_stem_obvious_negatives(stem)
    assert screen.not_obviously_negative
    assert screen.bass_instrument_proven is False
    assert screen.source_isolation_proven is False


def test_corrupt_truncated_short_and_unreadable_pcm_fail_closed(tmp_path):
    bad = _wav(tmp_path / "bad.wav", "bass")
    bad.write_bytes(bad.read_bytes()[:-2])
    assert screen_bass_stem_obvious_negatives(bad).status == "unavailable"
    assert screen_bass_stem_obvious_negatives(tmp_path / "missing.wav").status == "unavailable"

    short = tmp_path / "short.wav"
    with wave.open(str(short), "wb") as wav:
        wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(RATE)
        wav.writeframes(b"\x00\x00" * 50)
    assert screen_bass_stem_obvious_negatives(short).status == "unavailable"



def test_v6_qualified_bass_chart_is_stale_after_negative_control_revision(tmp_path):
    """An old cached symbolic_verified chart cannot bypass the added gate."""
    import json
    from rocksmith_cdlc_generator.reconciliation import (
        ReconciledBassChart, ReconciledBassNote, reconciled_bass_chart_is_current,
        CURRENT_RECONCILIATION_ALGORITHM_VERSION,
    )
    from rocksmith_cdlc_generator.source_import import SourceTrustClass

    assert CURRENT_RECONCILIATION_ALGORITHM_VERSION == 7
    note = ReconciledBassNote(
        start_seconds=0.5, duration_seconds=0.8, midi=28,
        status="verified_match", trust_class=SourceTrustClass.symbolic_verified,
        review_required=False, alignment_confidence=1.0,
        qualification_reasons=["QUALIFIED"],
        qualification_thresholds={"minimum_audio_confidence": .70},
    )
    chart = ReconciledBassChart(
        source_sha256="a" * 64, track_index=0,
        onset_tolerance_seconds=.15, verified_onset_tolerance_seconds=.08,
        notes=[note],
    )
    raw = chart.model_dump(mode="json")
    old = tmp_path / "pre-negative-screen.json"
    raw["reconciliation_algorithm_version"] = 6
    old.write_text(json.dumps(raw), encoding="utf-8")
    assert not reconciled_bass_chart_is_current(old)
    raw["reconciliation_algorithm_version"] = CURRENT_RECONCILIATION_ALGORITHM_VERSION
    new = tmp_path / "current-synthetic.json"
    new.write_text(json.dumps(raw), encoding="utf-8")
    assert reconciled_bass_chart_is_current(new)
