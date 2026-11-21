from __future__ import annotations

import json
from pathlib import Path
import wave

import pytest

from rocksmith_cdlc_generator.hashing import sha256_file
from rocksmith_cdlc_generator.stems import (
    StemArtifact, StemSeparationError, verified_project_stem, separate_project_bass,
)


def _audio(path: Path, frames: int = 250) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(44100)
        out.writeframes(b"\x00\x00" * frames)


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


def test_stem_rejects_unrelated_recording_even_when_geometry_matches(tmp_path: Path) -> None:
    original = tmp_path / "audio" / "normalized.wav"
    stem = tmp_path / "stems" / "guitar.wav"
    _audio(original)
    _audio(stem)
    receipt = tmp_path / "stems" / "guitar.json"
    receipt.write_text(json.dumps({
        "schema_version": 1, "instrument": "guitar",
        "source_sha256": "0" * 64, "output_sha256": sha256_file(stem),
    }), encoding="utf-8")
    with pytest.raises(StemSeparationError, match="stale"):
        verified_project_stem(tmp_path, "lead")
    with pytest.raises(StemSeparationError, match="stale"):
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
    artifact = separate_project_bass(tmp_path, model="fake-local-test")
    assert Path(artifact.path) == verified_project_stem(tmp_path, "bass")
    receipt = json.loads((tmp_path / "stems" / "bass.json").read_text(encoding="utf-8"))
    assert receipt["source_sha256"] == sha256_file(source)
    assert receipt["output_sha256"] == sha256_file(Path(artifact.path))
