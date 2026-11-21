"""A hash-bound Bass WAV cannot become a musical oracle by copying the mix."""
from __future__ import annotations

from array import array
import json
import math
from pathlib import Path
import shutil
import wave

import pytest

from rocksmith_cdlc_generator.auto_cdlc_truth import generate_known_truth
from rocksmith_cdlc_generator.hashing import sha256_file
from rocksmith_cdlc_generator.reconciliation import (
    is_verified_bass_stem_transcription, ReconciledBassChart,
    reconciled_bass_chart_is_current,
)
from rocksmith_cdlc_generator.stem_content_alignment import audit_stem_content_alignment
from rocksmith_cdlc_generator.stem_signal_distinctness import screen_stem_nontrivial_difference
from rocksmith_cdlc_generator.transcription import BassTranscription


def _write(path: Path, samples: array, *, rate: int = 8000) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(rate)
        output.writeframes(samples.tobytes())
    return path


@pytest.fixture
def bass_plus_weak_drums(tmp_path: Path):
    rate, duration = 8000, 8
    bass = array("h")
    mixture = array("h")
    drum_starts = (0.71, 1.48, 2.23, 3.17, 4.05, 5.29, 6.21, 7.09)
    for i in range(rate * duration):
        sec = i / rate
        bass_tone = 6000 * math.sin(2 * math.pi * 103 * sec)
        drum = 0.0
        for beat in drum_starts:
            elapsed = sec - beat
            if 0 <= elapsed < .10:
                drum += 2100 * math.sin(2 * math.pi * 950 * elapsed) * (1-elapsed/.10)
        bass.append(round(bass_tone))
        mixture.append(round(bass_tone + drum))
    return (
        _write(tmp_path / "master.wav", mixture, rate=rate),
        _write(tmp_path / "bass.wav", bass, rate=rate),
        mixture,
    )


def test_distinctness_screen_accepts_nontrivial_bass_and_drum_difference(bass_plus_weak_drums):
    source, bass, _mix = bass_plus_weak_drums
    result = screen_stem_nontrivial_difference(source, bass)
    assert result.status == "nontrivial_difference"
    assert result.distinct_windows >= 2
    assert result.evaluated_windows >= result.distinct_windows


def test_identical_bytes_and_gain_only_copy_never_prove_bass_distinctness(
    bass_plus_weak_drums, tmp_path: Path
):
    source, bass, mix = bass_plus_weak_drums
    exact = tmp_path / "exact.wav"
    shutil.copyfile(source, exact)
    assert screen_stem_nontrivial_difference(source, exact).status == "indistinguishable"
    for scale in (.5, -1.0):
        scaled = _write(tmp_path / f"gain-{scale}.wav", array("h", (
            round(sample * scale) for sample in mix
        )))
        result = screen_stem_nontrivial_difference(source, scaled)
        assert result.status != "nontrivial_difference"


def test_silent_and_too_short_signal_refuse_comparison(tmp_path: Path):
    quiet = _write(tmp_path / "quiet.wav", array("h", [0]) * 64000)
    other = _write(tmp_path / "quiet2.wav", array("h", [1]) * 64000)
    assert screen_stem_nontrivial_difference(quiet, other).status == "ambiguous"
    tiny = _write(tmp_path / "tiny.wav", array("h", [0]) * 20)
    assert screen_stem_nontrivial_difference(tiny, tiny).status != "nontrivial_difference"


def test_truncated_pcm_is_not_trusted_as_distinct(tmp_path: Path, bass_plus_weak_drums):
    source, bass, mix = bass_plus_weak_drums
    truncated = tmp_path / "cut.wav"
    truncated.write_bytes(bass.read_bytes()[:-2])
    assert screen_stem_nontrivial_difference(source, truncated).status == "incompatible"


def test_identical_full_mix_with_valid_receipt_and_clock_cannot_promote(
    tmp_path: Path,
):
    fixture = tmp_path / "truth"
    master, _truth = generate_known_truth(fixture)
    project = tmp_path / "project"
    original = project / "audio" / "normalized.wav"
    stem = project / "stems" / "bass.wav"
    original.parent.mkdir(parents=True)
    stem.parent.mkdir(parents=True)
    shutil.copyfile(master, original)
    shutil.copyfile(master, stem)
    receipt = project / "stems" / "bass.json"
    receipt.write_text(json.dumps({
        "schema_version": 1, "instrument": "bass",
        "source_sha256": sha256_file(original),
        "output_sha256": sha256_file(stem),
        "engine": "fake-perfect-separator", "model": "synthetic-test",
    }), encoding="utf-8")
    transcription = BassTranscription(
        engine="fixture", source_path=str(stem),
        sample_rate_hz=44100, source_sha256=sha256_file(stem), notes=[],
    )
    assert audit_stem_content_alignment(original, stem).status == "aligned"
    assert not is_verified_bass_stem_transcription(project, transcription)
    assert sha256_file(stem) == sha256_file(original)


def test_old_v4_verified_chart_is_stale_under_clone_guard(tmp_path: Path):
    payload = ReconciledBassChart(
        source_sha256="a" * 64, track_index=0,
        onset_tolerance_seconds=.15, verified_onset_tolerance_seconds=.08,
        notes=[],
    ).model_dump(mode="json")
    payload["reconciliation_algorithm_version"] = 4
    file = tmp_path / "old.json"
    file.write_text(json.dumps(payload), encoding="utf-8")
    assert not reconciled_bass_chart_is_current(file)
