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

    def __init__(self, *, model: str, use_directml: bool = False) -> None:
        if not model.strip():
            raise ValueError("A source-separation model filename is required")
        self.model = model
        self.use_directml = use_directml

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
        if self.use_directml:
            command.append("--use_directml")
        return command

    def separate(self, audio_path: Path, output_path: Path) -> StemArtifact:
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
            result = subprocess.run(command, capture_output=True, text=True)
            if result.returncode != 0:
                raise StemSeparationError(
                    "audio-separator failed with exit code "
                    f"{result.returncode}: {result.stderr.strip() or result.stdout.strip()}"
                )

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
) -> StemArtifact:
    project_dir = project_dir.resolve()
    source = project_dir / "audio" / "normalized.wav"
    if not source.is_file():
        raise FileNotFoundError(
            f"Normalized project audio not found: {source}. Run `cdlc normalize` first."
        )
    output = project_dir / "stems" / "bass.wav"
    separator = AudioSeparatorBassStemSeparator(
        model=model,
        use_directml=use_directml,
    )
    original_hash = sha256_file(source)
    artifact = separator.separate(source, output)
    if sha256_file(source) != original_hash:
        raise StemSeparationError("Original recording changed during stem separation")
    receipt_path = project_dir / "stems" / "bass.json"
    receipt = {
        "schema_version": 1,
        "instrument": "bass",
        "source_sha256": original_hash,
        "output_sha256": sha256_file(output),
        "engine": artifact.engine,
        "model": artifact.model,
    }
    temporary = receipt_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(receipt, sort_keys=True, indent=2), encoding="utf-8")
    os.replace(temporary, receipt_path)
    return artifact


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
