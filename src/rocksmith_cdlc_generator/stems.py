from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, Field

from .hashing import sha256_file
from .bass_separator_admission import inspect_bass_separator_readiness


class StemSeparationError(RuntimeError):
    pass


class StemArtifact(BaseModel):
    instrument: str
    path: str
    engine: str
    model: str
    sample_rate_hz: int = Field(default=44100, gt=0)


class BassStemSeparator(Protocol):
    name: str

    def separate(self, audio_path: Path, output_path: Path) -> StemArtifact:
        ...


class AudioSeparatorBassStemSeparator:
    """Adapter for the optional `audio-separator` CLI.

    The heavyweight source-separation package is intentionally not a core dependency.
    Users can install an appropriate CPU/GPU extra separately; this adapter keeps the
    project pipeline stable while the model/runtime can evolve independently.
    """

    name = "audio-separator"

    def __init__(
        self, *, model: str, use_directml: bool = False,
        model_file_dir: Path | None = None, timeout_seconds: int = 240,
        execution_authorized: bool = False,
    ) -> None:
        if not model.strip():
            raise ValueError("A source-separation model filename is required")
        if not 30 <= timeout_seconds <= 900:
            raise ValueError("Separator timeout must be between 30 and 900 seconds")
        self.model = model
        self.use_directml = use_directml
        self.model_file_dir = Path(model_file_dir).resolve() if model_file_dir else None
        self.timeout_seconds = timeout_seconds
        self.execution_authorized = execution_authorized

    def build_command(self, audio_path: Path, output_dir: Path) -> list[str]:
        executable = shutil.which("audio-separator")
        if executable is None:
            raise StemSeparationError(
                "audio-separator was not found on PATH. Install the optional local "
                "source-separation runtime before using this stage."
            )
        command = [
            executable,
            str(audio_path),
            "--model_filename",
            self.model,
            "--single_stem",
            "Bass",
            "--sample_rate",
            "44100",
            "--output_format",
            "WAV",
            "--output_dir",
            str(output_dir),
        ]
        if self.model_file_dir is not None:
            command.extend(["--model_file_dir", str(self.model_file_dir)])
        if self.use_directml:
            command.append("--use_directml")
        return command

    def separate(self, audio_path: Path, output_path: Path) -> StemArtifact:
        if not self.execution_authorized or self.model_file_dir is None:
            raise StemSeparationError("Explicit cached-model admission and execution consent required")
        audio_path = audio_path.resolve()
        if not audio_path.is_file():
            raise FileNotFoundError(audio_path)

        output_path = output_path.resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(
            prefix="bass-separation-", dir=output_path.parent
        ) as work_dir_name:
            work_dir = Path(work_dir_name)
            command = self.build_command(audio_path, work_dir)
            try:
                result = subprocess.run(
                    command, capture_output=True, text=True,
                    timeout=self.timeout_seconds, check=False,
                    env={**os.environ, "HF_HUB_OFFLINE": "1",
                         "TRANSFORMERS_OFFLINE": "1",
                         "AUDIO_SEPARATOR_MODEL_DIR": str(self.model_file_dir)},
                )
            except subprocess.TimeoutExpired as exc:
                raise StemSeparationError("LOCAL_SEPARATOR_TIMEOUT") from exc
            if result.returncode != 0:
                # Never propagate model logs containing private source paths or
                # accidental credentials into the project/CI report.
                raise StemSeparationError("LOCAL_SEPARATOR_PROCESS_FAILED")

            candidates = sorted(work_dir.glob("*.wav"))
            if len(candidates) != 1:
                raise StemSeparationError(
                    "Expected exactly one Bass WAV from audio-separator, found "
                    f"{len(candidates)} in {work_dir}."
                )
            shutil.copy2(candidates[0], output_path)

        return StemArtifact(
            instrument="bass",
            path=str(output_path),
            engine=self.name,
            model=self.model,
            sample_rate_hz=44100,
        )


def separate_project_bass(
    project_dir: Path,
    *,
    model: str,
    use_directml: bool = False,
    model_file_dir: Path | None = None,
    expected_model_sha256: str | None = None,
    model_rights_confirmed: bool = False,
    execute: bool = False,
    timeout_seconds: int = 240,
) -> StemArtifact:
    """Run a *short* explicitly approved local separation; never a silent download.

    This is not an unattended model installer or whole-song worker. A model
    cache can reference auxiliary upstream files/configs: the environment
    hints offline operation but is NOT OS-enforced network isolation.
    """
    project_dir = Path(project_dir).resolve()
    readiness = inspect_bass_separator_readiness(
        project_dir, model_filename=model, model_file_dir=model_file_dir,
        expected_model_sha256=expected_model_sha256,
        model_rights_confirmed=model_rights_confirmed,
    )
    if not execute:
        raise StemSeparationError("LOCAL_SEPARATOR_EXECUTION_NOT_AUTHORIZED")
    if not readiness.admitted:
        raise StemSeparationError(readiness.code)
    if not 30 <= timeout_seconds <= 900:
        raise StemSeparationError("INVALID_SEPARATOR_TIMEOUT")
    source = (project_dir / "audio" / "normalized.wav").resolve()
    if not source.is_relative_to(project_dir):
        raise StemSeparationError("LOCAL_SOURCE_PATH_OUTSIDE_PROJECT")
    output_dir = (project_dir / "stems").resolve()
    if not output_dir.is_relative_to(project_dir):
        raise StemSeparationError("LOCAL_STEM_OUTPUT_OUTSIDE_PROJECT")
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / "bass.wav"
    receipt_path = output_dir / "bass.json"
    cache = Path(model_file_dir).resolve()
    model_path = cache / model
    original_hash = readiness.source_sha256
    assert original_hash is not None

    separator = AudioSeparatorBassStemSeparator(
        model=model, use_directml=use_directml, model_file_dir=cache,
        timeout_seconds=timeout_seconds, execution_authorized=True,
    )
    # Keep previously validated output untouched until a new, fully
    # validated stem AND provenance receipt are ready in private staging.
    with tempfile.TemporaryDirectory(prefix="bass-separation-staging-", dir=output_dir) as staged_dir:
        stage = Path(staged_dir)
        candidate = stage / "bass.wav"
        artifact = separator.separate(source, candidate)
        if (
            sha256_file(source) != original_hash
            or sha256_file(model_path) != expected_model_sha256
        ):
            raise StemSeparationError("SOURCE_OR_CACHED_MODEL_CHANGED_DURING_SEPARATION")
        try:
            import wave
            with wave.open(str(source), "rb") as original_wav, wave.open(str(candidate), "rb") as stem_wav:
                source_geometry = (
                    original_wav.getframerate(), original_wav.getnchannels(),
                    original_wav.getsampwidth(), original_wav.getnframes(),
                    original_wav.getcomptype(),
                )
                stem_geometry = (
                    stem_wav.getframerate(), stem_wav.getnchannels(),
                    stem_wav.getsampwidth(), stem_wav.getnframes(),
                    stem_wav.getcomptype(),
                )
        except (wave.Error, EOFError, OSError) as exc:
            raise StemSeparationError("SEPARATOR_OUTPUT_NOT_PCM_WAV") from exc
        if source_geometry != stem_geometry or source_geometry[2] != 2 or source_geometry[4] != "NONE":
            raise StemSeparationError("SEPARATOR_OUTPUT_RECORDING_CLOCK_MISMATCH")
        stem_hash = sha256_file(candidate)
        receipt = {
            "schema_version": 1,
            "instrument": "bass",
            "source_sha256": original_hash,
            "output_sha256": stem_hash,
            "engine": artifact.engine,
            "model": artifact.model,
            "model_sha256": expected_model_sha256,
            "pilot_seconds": readiness.input_seconds,
            "separator_admission": "EXPLICIT_LOCAL_CACHED_MODEL",
            "network_isolation_proven": False,
        }
        receipt_staging = stage / "bass.json"
        receipt_staging.write_text(json.dumps(receipt, sort_keys=True, indent=2), encoding="utf-8")
        os.replace(candidate, output)
        os.replace(receipt_staging, receipt_path)
    return artifact.model_copy(update={"path": str(output)})


def verified_project_stem(project_dir: Path, role: str) -> Path:
    """Load only a stem tied by hash to this recording; legacy bare WAVs fail closed."""
    project = Path(project_dir).resolve()
    instrument = "bass" if role == "bass" else "guitar" if role in {"lead", "rhythm"} else None
    if instrument is None:
        raise StemSeparationError("Unknown instrument role")
    source = (project / "audio" / "normalized.wav").resolve()
    stem = (project / "stems" / f"{instrument}.wav").resolve()
    receipt = (project / "stems" / f"{instrument}.json").resolve()
    if not all(p.is_relative_to(project) for p in (source, stem, receipt)):
        raise StemSeparationError("Stem paths must remain inside the private project")
    if not source.is_file() or not stem.is_file() or not receipt.is_file():
        raise StemSeparationError("A verified local instrument stem and provenance receipt are required")
    try:
        data = json.loads(receipt.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise StemSeparationError("Malformed stem provenance receipt")
        if (
            data.get("schema_version") != 1
            or data.get("instrument") != instrument
            or data.get("source_sha256") != sha256_file(source)
            or data.get("output_sha256") != sha256_file(stem)
        ):
            raise StemSeparationError("Stem is stale or cannot be tied to the current recording")
    except (ValueError, TypeError, OSError) as exc:
        raise StemSeparationError("Malformed stem provenance receipt") from exc
    return stem
