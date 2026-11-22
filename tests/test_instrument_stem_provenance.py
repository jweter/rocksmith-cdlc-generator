from __future__ import annotations

import json
from pathlib import Path
import wave

import pytest

from rocksmith_cdlc_generator.hashing import sha256_file
from rocksmith_cdlc_generator.stems import (
    StemArtifact, StemSeparationError, verified_project_stem, separate_project_bass,
)


def _audio(path: Path, frames: int = 250, *, sample: int = 0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(44100)
        out.writeframes(sample.to_bytes(2, "little", signed=True) * frames)


def test_stem_requires_source_and_stem_hash_receipt(tmp_path: Path) -> None:
    original = tmp_path / "audio" / "normalized.wav"
    stem = tmp_path / "stems" / "bass.wav"
    _audio(original)
    _audio(stem)
    with pytest.raises(StemSeparationError, match="provenance receipt"):
        verified_project_stem(tmp_path, "bass")
    receipt = tmp_path / "stems" / "bass.json"
    payload = {
        "schema_version": 1, "instrument": "bass",
        "source_sha256": sha256_file(original),
        "output_sha256": sha256_file(stem),
        "engine": "test", "model": "fixture",
    }
    receipt.write_text(json.dumps(payload), encoding="utf-8")
    assert verified_project_stem(tmp_path, "bass") == stem
    _audio(stem, frames=251)
    with pytest.raises(StemSeparationError, match="stale"):
        verified_project_stem(tmp_path, "bass")


def _guitar_receipt(project: Path, role: str, *, sample: int) -> Path:
    stem = project / "stems" / f"{role}.wav"
    _audio(stem, sample=sample)
    original = project / "audio" / "normalized.wav"
    receipt = project / "stems" / f"{role}.json"
    receipt.write_text(json.dumps({
        "schema_version": 2,
        "instrument": role,
        "stem_role": role,
        "source_kind": "role_specific_stem",
        "source_sha256": sha256_file(original),
        "output_sha256": sha256_file(stem),
        "engine": "synthetic-test", "model": "synthetic-no-inference",
    }), encoding="utf-8")
    return stem


def test_generic_guitar_stem_cannot_masquerade_as_lead_or_rhythm(tmp_path: Path) -> None:
    original = tmp_path / "audio" / "normalized.wav"
    _audio(original, sample=11)
    stem = _guitar_receipt(tmp_path, "lead", sample=12)
    # Legacy generic guitar media and receipt are not acceptable role sources.
    generic = tmp_path / "stems" / "guitar.wav"
    _audio(generic, sample=13)
    (tmp_path / "stems" / "guitar.json").write_text(json.dumps({
        "schema_version": 1, "instrument": "guitar",
        "source_sha256": sha256_file(original), "output_sha256": sha256_file(generic),
    }), encoding="utf-8")
    assert verified_project_stem(tmp_path, "lead") == stem
    with pytest.raises(StemSeparationError, match="provenance receipt"):
        verified_project_stem(tmp_path, "rhythm")


def test_lead_and_rhythm_require_independent_role_and_recording_receipts(tmp_path: Path) -> None:
    original = tmp_path / "audio" / "normalized.wav"
    _audio(original, sample=101)
    lead = _guitar_receipt(tmp_path, "lead", sample=102)
    rhythm = _guitar_receipt(tmp_path, "rhythm", sample=103)
    assert verified_project_stem(tmp_path, "lead") == lead
    assert verified_project_stem(tmp_path, "rhythm") == rhythm
    # Changing one role cannot be covered by the other's previously valid receipt.
    _audio(lead, sample=104)
    with pytest.raises(StemSeparationError, match="stale"):
        verified_project_stem(tmp_path, "lead")
    assert verified_project_stem(tmp_path, "rhythm") == rhythm
    _audio(original, sample=105)
    with pytest.raises(StemSeparationError, match="stale"):
        verified_project_stem(tmp_path, "rhythm")


@pytest.mark.parametrize("tamper", [
    {"schema_version": 1}, {"schema_version": True}, {"instrument": "rhythm"},
    {"stem_role": "rhythm"}, {"source_kind": "generic_guitar"},
])
def test_guitar_stem_role_contract_fails_closed(tmp_path: Path, tamper: dict) -> None:
    _audio(tmp_path / "audio" / "normalized.wav", sample=201)
    _guitar_receipt(tmp_path, "lead", sample=202)
    receipt = tmp_path / "stems" / "lead.json"
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    payload.update(tamper)
    receipt.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(StemSeparationError):
        verified_project_stem(tmp_path, "lead")


def test_guitar_stem_rejects_full_mix_clone_and_duplicate_roles(tmp_path: Path) -> None:
    original = tmp_path / "audio" / "normalized.wav"
    _audio(original, sample=301)
    _guitar_receipt(tmp_path, "lead", sample=301)
    with pytest.raises(StemSeparationError, match="full-mix clone"):
        verified_project_stem(tmp_path, "lead")
    _guitar_receipt(tmp_path, "lead", sample=302)
    _guitar_receipt(tmp_path, "rhythm", sample=302)
    with pytest.raises(StemSeparationError, match="identical across distinct roles"):
        verified_project_stem(tmp_path, "lead")
    with pytest.raises(StemSeparationError, match="identical across distinct roles"):
        verified_project_stem(tmp_path, "rhythm")


def test_separation_writes_hash_bound_receipt(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "audio" / "normalized.wav"
    _audio(source)
    def fake_separate(self, _source: Path, output: Path) -> StemArtifact:
        _audio(output)
        return StemArtifact(
            instrument="bass", path=str(output),
            engine="synthetic-test", model="fake-local-test",
        )
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.stems.AudioSeparatorBassStemSeparator.separate",
        fake_separate,
    )
    # Existing receipt test now uses explicit model and resource admission;
    # no real model/network/runtime is loaded by the monkeypatched separator.
    cache = tmp_path / "cache"
    cache.mkdir()
    model = cache / "fake-local-test.onnx"
    model.write_bytes(b"synthetic-model-fixture")
    manifest = cache / "model-manifest.json"
    manifest.write_text(json.dumps({
        "schema_version": 1,
        "model_filename": model.name,
        "files": [
            {"path": model.name, "sha256": sha256_file(model),
             "size_bytes": model.stat().st_size},
        ],
    }), encoding="utf-8")
    from types import SimpleNamespace
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.bass_separator_admission.available_memory_gib",
        lambda: 12.0,
    )
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.bass_separator_admission.shutil.disk_usage",
        lambda _: SimpleNamespace(free=20 * 1024**3),
    )
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.bass_separator_admission.shutil.which",
        lambda _: "audio-separator",
    )
    artifact = separate_project_bass(
        tmp_path, model=model.name, model_file_dir=cache,
        model_manifest_path=manifest, expected_model_sha256=sha256_file(model),
        model_rights_confirmed=True, execute=True,
    )
    assert Path(artifact.path) == verified_project_stem(tmp_path, "bass")
    receipt = json.loads((tmp_path / "stems" / "bass.json").read_text(encoding="utf-8"))
    assert receipt["source_sha256"] == sha256_file(source)
    assert receipt["output_sha256"] == sha256_file(Path(artifact.path))
