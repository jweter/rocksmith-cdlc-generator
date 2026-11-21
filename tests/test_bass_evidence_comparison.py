"""Synthetic comparison contracts. No separator, real model or private media is run."""
from __future__ import annotations

import json
from pathlib import Path
import shutil

import pytest

from rocksmith_cdlc_generator.auto_cdlc_truth import generate_known_truth, verify_known_truth
from rocksmith_cdlc_generator.bass_evidence_comparison import (
    BassEvidenceBenchmarkError,
    compare_bass_evidence_sources,
)
from rocksmith_cdlc_generator.hashing import sha256_file
from rocksmith_cdlc_generator.transcription import BassTranscription, NoteEvent


@pytest.fixture
def setup(tmp_path: Path):
    fixture = tmp_path / "known-truth"
    master, truth_file = generate_known_truth(fixture)
    project = tmp_path / "project"
    original = project / "audio" / "normalized.wav"
    original.parent.mkdir(parents=True)
    shutil.copyfile(master, original)
    output = project / "analysis" / "comparison.json"
    return fixture, project, output


def _fake_notes(path: Path, truth: dict, *, confident: bool) -> BassTranscription:
    events = [
        NoteEvent(
            start=n["onset_seconds"], duration=n["duration_seconds"],
            midi=n["midi"], confidence=.97 if confident else .30,
            pitch_confidence=.97 if confident else .25,
            timing_confidence=.97 if confident else .20,
            review_required=not confident,
        ) for n in truth["bass_notes"]
    ]
    return BassTranscription(
        engine="synthetic-stand-in-NOT-real-pYIN",
        source_path=str(path),
        source_sha256=sha256_file(path), sample_rate_hz=44100,
        notes=events,
    )


def _prepared_sources(fixture: Path, project: Path) -> Path:
    original, _truth = verify_known_truth(fixture)
    master = project / "audio" / "normalized.wav"
    focus = project / "audio" / "derived" / "instrument_focus" / "prepared.wav"
    focus.parent.mkdir(parents=True)
    shutil.copyfile(original, focus)
    focus.with_suffix(".json").write_text(json.dumps({
        "parameters": {"role": "bass", "tuning_midi": [28,33,38,43],
                       "source_sha256": sha256_file(master)},
        "output_sha256": sha256_file(focus),
    }), encoding="utf-8")
    stem = project / "stems" / "bass.wav"
    stem.parent.mkdir(parents=True)
    shutil.copyfile(original, stem)
    (project / "stems" / "bass.json").write_text(json.dumps({
        "schema_version": 1, "instrument": "bass",
        "source_sha256": sha256_file(master),
        "output_sha256": sha256_file(stem),
        "engine": "synthetic-test", "model": "not-a-real-separator",
    }), encoding="utf-8")
    return focus


def test_readiness_never_imports_or_calls_transcriber(setup) -> None:
    fixture, project, out = setup
    def not_allowed(path: Path):
        raise AssertionError("Readiness must not load pYIN or another model")
    result = compare_bass_evidence_sources(
        fixture, project, out, transcriber=not_allowed
    )
    assert result["comparison_verdict"] == "READINESS_ONLY"
    assert result["resource_preflight"]["status"] == "READINESS_ONLY"
    assert result["source_results"]["original"]["status"] == "READY"
    assert result["source_results"]["focused"]["status"] == "UNAVAILABLE"
    assert result["source_results"]["stem"]["status"] == "UNAVAILABLE"
    assert out.is_file()
    assert "local" not in out.read_text(encoding="utf-8").lower()


def test_resource_gate_blocks_even_valid_synthetic_sources(setup) -> None:
    fixture, project, out = setup
    _prepared_sources(fixture, project)
    def not_allowed(path: Path):
        raise AssertionError("No CPU analysis without available physical RAM")
    result = compare_bass_evidence_sources(
        fixture, project, out, execute=True, memory_probe=lambda: 2.0,
        transcriber=not_allowed,
    )
    assert result["resource_preflight"]["status"] == "BLOCKED_RESOURCES"
    assert result["comparison_verdict"] == "BLOCKED_OR_UNQUALIFIED"
    assert all(item["raw_note_f1"] is None for item in result["source_results"].values())


def test_scores_three_sources_but_never_claims_separation_or_game_pass(setup) -> None:
    fixture, project, out = setup
    focus = _prepared_sources(fixture, project)
    truth = verify_known_truth(fixture)[1]
    invoked = []
    def simulated(path: Path):
        invoked.append(path)
        return _fake_notes(path, truth, confident=path.name == "bass.wav")
    result = compare_bass_evidence_sources(
        fixture, project, out, focused_path=focus, execute=True,
        memory_probe=lambda: 12.0, transcriber=simulated,
    )
    assert len(invoked) == 3
    assert result["comparison_verdict"] == "COMPARISON_SCORED"
    assert result["source_results"]["original"]["raw_note_f1"] == 1.0
    assert result["source_results"]["original"]["qualified_f1"] == 0.0
    assert result["source_results"]["focused"]["qualified_f1"] == 0.0
    assert result["source_results"]["stem"]["qualified_f1"] == 1.0
    assert result["source_results"]["stem"]["reason"] == "STEM_CLOCK_ALIGNED"
    assert result["source_separation_purity"] == "NOT_PROVEN"
    assert result["gameplay_acceptance"] == "NOT_PROVEN"
    assert result["musical_acceptance"] == "NOT_PROVEN"
    assert all(value["peak_process_ram_gib"] is None for value in result["source_results"].values())
    text = out.read_text(encoding="utf-8")
    assert str(fixture) not in text and str(project) not in text
    assert "synthetic-stand-in" not in text


def test_replaces_unbound_transcription_with_unqualified_result(setup) -> None:
    fixture, project, out = setup
    truth = verify_known_truth(fixture)[1]
    def fake(path: Path):
        return _fake_notes(path, truth, confident=True).model_copy(
            update={"source_sha256": "0" * 64}
        )
    result = compare_bass_evidence_sources(
        fixture, project, out, execute=True, memory_probe=lambda: 10,
        transcriber=fake,
    )
    row = result["source_results"]["original"]
    assert row["status"] == "UNQUALIFIED"
    assert row["reason"] == "TRANSCRIPTION_INPUT_HASH_UNPROVEN"
    assert row["qualified_f1"] is None


def test_mismatched_master_or_stale_focused_receipt_never_scores(setup) -> None:
    fixture, project, out = setup
    focus = _prepared_sources(fixture, project)
    source = project / "audio" / "normalized.wav"
    source.write_bytes(b"different song")
    with pytest.raises(BassEvidenceBenchmarkError, match="PROJECT_SOURCE_DIFFERS"):
        compare_bass_evidence_sources(fixture, project, out)
    assert not out.exists()
    master, _ = verify_known_truth(fixture)
    shutil.copyfile(master, source)
    focus.with_suffix(".json").write_text(json.dumps({
        "parameters": {"role": "bass", "tuning_midi": [28, 33, 38, 43],
                       "source_sha256": "b" * 64},
        "output_sha256": sha256_file(focus)
    }))
    result = compare_bass_evidence_sources(fixture, project, out, focused_path=focus)
    assert result["source_results"]["focused"]["status"] == "UNAVAILABLE"
    assert result["source_results"]["focused"]["reason"] == "FOCUSED_RECEIPT_MISMATCH"


def test_missing_or_stale_stem_never_counts_as_verified_separation(setup) -> None:
    fixture, project, out = setup
    _prepared_sources(fixture, project)
    (project / "stems" / "bass.wav").write_bytes(b"modified")
    result = compare_bass_evidence_sources(fixture, project, out)
    assert result["source_results"]["stem"]["status"] == "UNAVAILABLE"
    assert result["source_results"]["stem"]["reason"] == "VERIFIED_STEM_UNAVAILABLE"


def test_cli_is_explicit_opt_in(setup) -> None:
    from rocksmith_cdlc_generator.bass_evidence_comparison_cli import build_parser
    fixture, project, out = setup
    args = build_parser().parse_args([
        "--fixture-dir", str(fixture),
        "--project-dir", str(project),
        "--out", str(out),
    ])
    assert args.execute is False
    assert args.focused_wav is None


def test_shifting_stem_content_cannot_make_it_a_ready_oracle(setup) -> None:
    from array import array
    import wave

    fixture, project, out = setup
    _prepared_sources(fixture, project)
    stem = project / "stems" / "bass.wav"
    with wave.open(str(stem), "rb") as audio:
        rate, frames = audio.getframerate(), audio.getnframes()
        samples = array("h")
        samples.frombytes(audio.readframes(frames))
    lag = round(0.2 * rate)
    altered = array("h", [0]) * lag + samples[:-lag]
    with wave.open(str(stem), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(rate)
        audio.writeframes(altered.tobytes())
    receipt = project / "stems" / "bass.json"
    data = json.loads(receipt.read_text(encoding="utf-8"))
    data["output_sha256"] = sha256_file(stem)
    receipt.write_text(json.dumps(data), encoding="utf-8")
    result = compare_bass_evidence_sources(fixture, project, out)
    assert result["source_results"]["stem"]["status"] == "UNQUALIFIED_CLOCK"
    assert result["source_results"]["stem"]["reason"] == "STEM_CLOCK_SHIFTED"


def test_each_opt_in_source_rechecks_actual_available_physical_ram(setup) -> None:
    fixture, project, out = setup
    _prepared_sources(fixture, project)
    truth = verify_known_truth(fixture)[1]
    calls = [8.0, 8.0, 1.0, 1.0]
    invoked = []
    def probe() -> float:
        return calls.pop(0)
    def fake(path: Path):
        invoked.append(path)
        return _fake_notes(path, truth, confident=True)
    result = compare_bass_evidence_sources(
        fixture, project, out, execute=True,
        focused_path=project / "audio/derived/instrument_focus/prepared.wav",
        memory_probe=probe, transcriber=fake,
    )
    assert len(invoked) == 1
    assert result["source_results"]["original"]["status"] == "SCORED_REVIEW_ONLY"
    assert result["source_results"]["focused"]["status"] == "BLOCKED_RESOURCES"
    assert result["source_results"]["stem"]["status"] == "BLOCKED_RESOURCES"
