from pathlib import Path

import pytest

from rocksmith_cdlc_generator import unattended_evidence_repair


def test_existing_bass_evidence_is_never_overwritten(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    evidence = tmp_path / "analysis" / "bass_raw.json"
    evidence.parent.mkdir()
    evidence.write_text("existing", encoding="utf-8")

    def fail(*args, **kwargs):
        raise AssertionError("transcription must not run when evidence already exists")

    monkeypatch.setattr(unattended_evidence_repair, "analyze_project_bass", fail)
    assert unattended_evidence_repair.ensure_bass_timing_evidence(tmp_path) is False
    assert evidence.read_text(encoding="utf-8") == "existing"


def test_missing_normalized_audio_fails_closed_without_transcription(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        unattended_evidence_repair,
        "analyze_project_bass",
        lambda *args, **kwargs: pytest.fail("transcription must not run without normalized audio"),
    )
    assert unattended_evidence_repair.ensure_bass_timing_evidence(tmp_path) is False


def test_missing_bass_evidence_is_generated_from_normalized_audio(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    audio = tmp_path / "audio" / "normalized.wav"
    audio.parent.mkdir()
    audio.write_bytes(b"fixture")
    evidence = tmp_path / "analysis" / "bass_raw.json"

    def generate(project: Path, *, engine: str, input_path: Path):
        assert project == tmp_path.resolve()
        assert engine == "librosa-pyin"
        assert input_path == audio
        evidence.parent.mkdir()
        evidence.write_text("generated", encoding="utf-8")
        return {"raw": evidence}

    monkeypatch.setattr(unattended_evidence_repair, "analyze_project_bass", generate)
    assert unattended_evidence_repair.ensure_bass_timing_evidence(tmp_path) is True
    assert evidence.is_file()
