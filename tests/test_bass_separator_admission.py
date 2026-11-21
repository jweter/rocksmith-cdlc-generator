"""No model or network calls: validate short, pinned and rights-confirmed separation."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import json
import wave

import pytest

from rocksmith_cdlc_generator.bass_separator_admission import (
    BassSeparatorReadiness, inspect_bass_separator_readiness,
    MAX_PILOT_SECONDS,
)
from rocksmith_cdlc_generator.hashing import sha256_file
from rocksmith_cdlc_generator.stems import (
    StemSeparationError, StemArtifact, separate_project_bass,
    AudioSeparatorBassStemSeparator,
)


def _wav(path: Path, *, seconds: float = 0.5, frames_extra: int = 0) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(44100)
        output.writeframes(bytes((1, 0)) * (round(seconds * 44100) + frames_extra))
    return path


@pytest.fixture
def ready_environment(tmp_path: Path, monkeypatch):
    project = tmp_path / "private-song"
    source = _wav(project / "audio" / "normalized.wav")
    cache = tmp_path / "models"
    cache.mkdir()
    model = cache / "bass.onnx"
    model.write_bytes(b"synthetic-cached-model-test-only")
    monkeypatch.setattr("rocksmith_cdlc_generator.bass_separator_admission.available_memory_gib", lambda: 10.0)
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.bass_separator_admission.shutil.disk_usage",
        lambda _: SimpleNamespace(free=20 * 1024**3),
    )
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.bass_separator_admission.shutil.which",
        lambda _: "/fake/audio-separator",
    )
    return project, source, cache, model


def _kwargs(cache: Path, model: Path) -> dict:
    return dict(
        model_filename=model.name,
        model_file_dir=cache,
        expected_model_sha256=sha256_file(model),
        model_rights_confirmed=True,
    )


def test_default_readiness_has_no_implicit_model_download_or_execution(ready_environment) -> None:
    project, source, cache, model = ready_environment
    report = inspect_bass_separator_readiness(project, model_filename=model.name)
    assert not report.admitted
    assert report.code == "EXPLICIT_MODEL_CACHE_REQUIRED"
    assert report.public_dict()["network_isolation_proven"] is False
    assert report.public_dict()["separator_model_quality_proven"] is False
    assert source.is_file() and model.is_file()


@pytest.mark.parametrize("change,reason", [
    ({"expected_model_sha256": "0" * 64}, "CACHED_MODEL_HASH_MISMATCH"),
    ({"expected_model_sha256": None}, "MODEL_SHA256_PIN_REQUIRED"),
    ({"model_filename": "../bass.onnx"}, "INVALID_MODEL_FILENAME"),
    ({"model_filename": "bass.yaml"}, "INVALID_MODEL_FILENAME"),
    ({"model_rights_confirmed": False}, "MODEL_LICENSE_CONFIRMATION_REQUIRED"),
])
def test_uncertified_or_ambiguous_model_is_blocked(
    ready_environment, change: dict, reason: str
) -> None:
    project, source, cache, model = ready_environment
    kwargs = _kwargs(cache, model)
    kwargs.update(change)
    report = inspect_bass_separator_readiness(project, **kwargs)
    assert report.status == "BLOCKED"
    assert report.code == reason


def test_real_available_ram_not_total_installed_ram_controls_admission(
    ready_environment, monkeypatch
) -> None:
    project, source, cache, model = ready_environment
    kwargs = _kwargs(cache, model)
    report = inspect_bass_separator_readiness(project, **kwargs, memory_probe=lambda: 5.87)
    assert report.code == "INSUFFICIENT_AVAILABLE_PHYSICAL_RAM"
    assert report.available_ram_gib == pytest.approx(5.87)
    assert not report.admitted
    allowed = inspect_bass_separator_readiness(project, **kwargs)
    assert allowed.admitted


def test_missing_runtime_and_excessive_song_length_fail_closed(
    ready_environment, monkeypatch
) -> None:
    project, source, cache, model = ready_environment
    kwargs = _kwargs(cache, model)
    monkeypatch.setattr("rocksmith_cdlc_generator.bass_separator_admission.shutil.which", lambda _: None)
    assert inspect_bass_separator_readiness(project, **kwargs).code == "AUDIO_SEPARATOR_NOT_INSTALLED"
    monkeypatch.setattr("rocksmith_cdlc_generator.bass_separator_admission.shutil.which", lambda _: "audio-separator")
    _wav(source, seconds=MAX_PILOT_SECONDS + 0.2)
    assert inspect_bass_separator_readiness(project, **kwargs).code == "FULL_SONG_EXECUTION_NOT_AUTHORIZED"


def test_header_lying_about_frame_count_is_rejected_not_silently_admitted(
    ready_environment,
) -> None:
    """A crash/full-disk can truncate the PCM payload while leaving the RIFF
    header's declared frame count unchanged. A file-size-only heuristic can
    miss this when the lost tail is smaller than the WAV header itself, so
    the real last declared frame must be probed directly."""
    project, source, cache, model = ready_environment
    kwargs = _kwargs(cache, model)
    intact = source.read_bytes()
    # Strip a few PCM bytes from the tail without touching the 44-byte header,
    # so getnframes() still reports the original (now inaccurate) count.
    source.write_bytes(intact[:-4])
    report = inspect_bass_separator_readiness(project, **kwargs)
    assert report.status == "BLOCKED"
    assert report.code == "TRUNCATED_INPUT_PCM"


def test_refuse_executing_model_when_only_readiness_was_requested(
    ready_environment, monkeypatch
) -> None:
    project, source, cache, model = ready_environment
    def must_never_call(*args, **kwargs):
        raise AssertionError("No model should launch without execute")
    monkeypatch.setattr(AudioSeparatorBassStemSeparator, "separate", must_never_call)
    with pytest.raises(StemSeparationError, match="EXECUTION_NOT_AUTHORIZED"):
        separate_project_bass(
            project, model=model.name, model_file_dir=cache,
            expected_model_sha256=sha256_file(model),
            model_rights_confirmed=True,
        )
    assert not (project / "stems").exists()


def test_validated_private_staged_output_and_receipt_commit_atomically(
    ready_environment, monkeypatch
) -> None:
    project, source, cache, model = ready_environment
    before = source.read_bytes()
    def fake_separate(self, original: Path, output: Path) -> StemArtifact:
        _wav(output)
        return StemArtifact(instrument="bass", path=str(output), engine="synthetic-test", model=self.model)
    monkeypatch.setattr(AudioSeparatorBassStemSeparator, "separate", fake_separate)
    result = separate_project_bass(
        project, model=model.name, model_file_dir=cache,
        expected_model_sha256=sha256_file(model),
        model_rights_confirmed=True, execute=True,
    )
    stem = project / "stems" / "bass.wav"
    receipt = json.loads((project / "stems" / "bass.json").read_text(encoding="utf-8"))
    assert result.path == str(stem)
    assert receipt["model_sha256"] == sha256_file(model)
    assert receipt["source_sha256"] == sha256_file(source)
    assert receipt["output_sha256"] == sha256_file(stem)
    assert receipt["network_isolation_proven"] is False
    assert source.read_bytes() == before


def test_invalid_model_output_preserves_previous_bass_stem_and_receipt(
    ready_environment, monkeypatch
) -> None:
    project, source, cache, model = ready_environment
    existing = _wav(project / "stems" / "bass.wav")
    prior_receipt = project / "stems" / "bass.json"
    prior_receipt.write_text('{"old":"verified"}', encoding="utf-8")
    saved_audio, saved_receipt = existing.read_bytes(), prior_receipt.read_bytes()

    def fake_bad_output(self, original: Path, output: Path) -> StemArtifact:
        _wav(output, frames_extra=1)
        return StemArtifact(instrument="bass", path=str(output), engine="synthetic", model=self.model)

    monkeypatch.setattr(AudioSeparatorBassStemSeparator, "separate", fake_bad_output)
    with pytest.raises(StemSeparationError, match="CLOCK_MISMATCH"):
        separate_project_bass(
            project, model=model.name, model_file_dir=cache,
            expected_model_sha256=sha256_file(model), model_rights_confirmed=True,
            execute=True,
        )
    assert existing.read_bytes() == saved_audio
    assert prior_receipt.read_bytes() == saved_receipt


def test_cli_separation_is_readiness_only_without_explicit_execute(
    ready_environment, monkeypatch, capsys
) -> None:
    from rocksmith_cdlc_generator.cli import build_parser
    project, source, cache, model = ready_environment
    parsed = build_parser().parse_args([
        "separate-bass", str(project), "--model", model.name,
        "--model-cache-dir", str(cache),
        "--model-sha256", sha256_file(model),
        "--confirm-model-rights",
    ])
    assert parsed.execute is False
    assert parsed.model_cache_dir == cache
    assert parsed.timeout == 240


def test_actual_adapter_requires_explicit_execution_authority(
    ready_environment,
) -> None:
    project, source, cache, model = ready_environment
    adapter = AudioSeparatorBassStemSeparator(
        model=model.name, model_file_dir=cache, execution_authorized=False,
    )
    with pytest.raises(StemSeparationError, match="execution consent"):
        adapter.separate(source, project / "stems" / "bass.wav")
    cmd = adapter.build_command(source, project)
    assert cmd[cmd.index("--model_file_dir") + 1] == str(cache.resolve())
    assert "--single_stem" in cmd


def test_receipt_commit_failure_restores_previous_audio_and_receipt(
    ready_environment, monkeypatch
) -> None:
    import os
    project, source, cache, model = ready_environment
    prior_audio = _wav(project / "stems" / "bass.wav")
    prior_receipt = project / "stems" / "bass.json"
    prior_receipt.write_text('{"prior":"valid"}', encoding="utf-8")
    original_wav, original_json = prior_audio.read_bytes(), prior_receipt.read_bytes()

    def fake_separate(self, original: Path, output: Path) -> StemArtifact:
        _wav(output)
        return StemArtifact(instrument="bass", path=str(output), engine="fixture", model=self.model)

    monkeypatch.setattr(AudioSeparatorBassStemSeparator, "separate", fake_separate)
    genuine_replace = os.replace
    failed_once = False

    def fail_receipt_once(src, dst):
        nonlocal failed_once
        if Path(dst) == prior_receipt and not failed_once:
            failed_once = True
            raise OSError("simulated receipt commit failure")
        return genuine_replace(src, dst)

    monkeypatch.setattr("rocksmith_cdlc_generator.stems.os.replace", fail_receipt_once)
    with pytest.raises(StemSeparationError, match="PREVIOUS_OUTPUT_RESTORED"):
        separate_project_bass(
            project, model=model.name, model_file_dir=cache,
            expected_model_sha256=sha256_file(model),
            model_rights_confirmed=True, execute=True,
        )
    assert failed_once
    assert prior_audio.read_bytes() == original_wav
    assert prior_receipt.read_bytes() == original_json


def test_truncated_pcm_payload_cannot_replace_an_existing_stem(
    ready_environment, monkeypatch
) -> None:
    project, source, cache, model = ready_environment
    previous = _wav(project / "stems" / "bass.wav")
    previous_receipt = project / "stems" / "bass.json"
    previous_receipt.write_text('{"verified":"previous"}', encoding="utf-8")
    old_audio, old_receipt = previous.read_bytes(), previous_receipt.read_bytes()

    def fake_header_only(self, original: Path, output: Path) -> StemArtifact:
        _wav(output)
        # Preserve the 44-byte WAV header, including its advertised 0.5s
        # frame count, but discard the declared data chunk's actual PCM bytes.
        output.write_bytes(output.read_bytes()[:44])
        return StemArtifact(instrument="bass", path=str(output), engine="synthetic", model=self.model)

    monkeypatch.setattr(AudioSeparatorBassStemSeparator, "separate", fake_header_only)
    with pytest.raises(StemSeparationError, match="SEPARATOR_OUTPUT_TRUNCATED_PCM"):
        separate_project_bass(
            project, model=model.name, model_file_dir=cache,
            expected_model_sha256=sha256_file(model), model_rights_confirmed=True,
            execute=True,
        )
    assert previous.read_bytes() == old_audio
    assert previous_receipt.read_bytes() == old_receipt
