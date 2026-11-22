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
from .model_bundle_manifest import inspect_cached_model_bundle
from .host_concurrency_admission import inspect_host_concurrency


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
            # The prior preflight can become stale while other Windows/laptop
            # workloads consume physical RAM. Sample a short, bounded host
            # window at the final launch boundary, never relying on a prior
            # cached PASS to authorize a potentially heavy subprocess.
            host = inspect_host_concurrency()
            if not host.admitted:
                raise StemSeparationError(host.code)
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
    model_manifest_path: Path | None = None,
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
        model_manifest_path=model_manifest_path,
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
        bundle = inspect_cached_model_bundle(
            cache, model_manifest_path, model_filename=model,
            expected_model_sha256=expected_model_sha256,
        )
        if (
            sha256_file(source) != original_hash
            or sha256_file(model_path) != expected_model_sha256
            or bundle.status != "VERIFIED_DECLARED_FILES"
            or bundle.manifest_sha256 != readiness.manifest_sha256
        ):
            raise StemSeparationError("SOURCE_OR_MODEL_BUNDLE_CHANGED_DURING_SEPARATION")
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
                # RIFF headers can advertise a correct frame count even when
                # the output PCM payload is missing or truncated. Inspect the
                # *last declared frame* rather than trusting getnframes().
                if stem_wav.getnframes() <= 0:
                    raise StemSeparationError("SEPARATOR_OUTPUT_TRUNCATED_PCM")
                stem_wav.setpos(stem_wav.getnframes() - 1)
                if len(stem_wav.readframes(1)) != stem_wav.getnchannels() * stem_wav.getsampwidth():
                    raise StemSeparationError("SEPARATOR_OUTPUT_TRUNCATED_PCM")
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
            "model_manifest_sha256": readiness.manifest_sha256,
            "model_manifest_verified_files": readiness.manifest_verified_files,
            "pilot_seconds": readiness.input_seconds,
            "separator_admission": "EXPLICIT_LOCAL_CACHED_MODEL",
            "network_isolation_proven": False,
        }
        receipt_staging = stage / "bass.json"
        receipt_staging.write_text(json.dumps(receipt, sort_keys=True, indent=2), encoding="utf-8")
        if output.is_symlink() or receipt_path.is_symlink():
            raise StemSeparationError("EXISTING_STEM_OR_RECEIPT_SYMLINK_UNSAFE")
        # A WAV and its provenance JSON are not one atomic filesystem object.
        # Back up the existing verified pair before the two replacements and
        # attempt rollback if either replacement fails. A crash between two
        # renames still fails closed at verified_project_stem() via SHA-256.
        prior_audio, prior_receipt = stage / "prior.wav", stage / "prior.json"
        # Finish BOTH backups before attempting either replacement, so a
        # failed backup can never erase the old receipt during rollback.
        if output.is_file():
            shutil.copy2(output, prior_audio)
        if receipt_path.is_file():
            shutil.copy2(receipt_path, prior_receipt)
        try:
            os.replace(candidate, output)
            os.replace(receipt_staging, receipt_path)
        except OSError as exc:
            try:
                if prior_audio.is_file():
                    os.replace(prior_audio, output)
                else:
                    output.unlink(missing_ok=True)
                if prior_receipt.is_file():
                    os.replace(prior_receipt, receipt_path)
                else:
                    receipt_path.unlink(missing_ok=True)
            except OSError:
                raise StemSeparationError("STEM_COMMIT_FAILED_ROLLBACK_UNCERTAIN") from exc
            raise StemSeparationError("STEM_COMMIT_FAILED_PREVIOUS_OUTPUT_RESTORED") from exc
    return artifact.model_copy(update={"path": str(output)})


def verified_project_stem(project_dir: Path, role: str) -> Path:
    """Resolve only an *exact-role*, hash-bound local audio candidate.

    Bass retains its historical v1 receipt. Lead and Rhythm require independent
    v2 role-specific receipts and paths; a generic guitar.wav is never an alias
    for either role. A valid receipt proves identity/provenance of the bytes,
    NOT that the sound contains only the stated instrument or that the notes
    match a score. The audition UI must not promote musical authority from it.
    """
    if role not in {"bass", "lead", "rhythm"}:
        raise StemSeparationError("Unknown instrument role")
    project = Path(project_dir).resolve()
    source = (project / "audio" / "normalized.wav").resolve()
    stem_candidate = project / "stems" / f"{role}.wav"
    receipt_candidate = project / "stems" / f"{role}.json"
    if stem_candidate.is_symlink() or receipt_candidate.is_symlink():
        raise StemSeparationError("Role stem and receipt cannot be symlink aliases")
    stem = stem_candidate.resolve()
    receipt = receipt_candidate.resolve()
    if not all(p.is_relative_to(project) for p in (source, stem, receipt)):
        raise StemSeparationError("Stem paths must remain inside the private project")
    if not source.is_file() or not stem.is_file() or not receipt.is_file():
        raise StemSeparationError("A verified local instrument stem and provenance receipt are required")
    try:
        data = json.loads(receipt.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise StemSeparationError("Malformed stem provenance receipt")
        original_hash = sha256_file(source)
        output_hash = sha256_file(stem)
        if (
            type(data.get("schema_version")) is not int
            or data["schema_version"] != (1 if role == "bass" else 2)
            or data.get("instrument") != role
            or data.get("source_sha256") != original_hash
            or data.get("output_sha256") != output_hash
        ):
            raise StemSeparationError("Stem is stale or cannot be tied to the current recording and role")
        if role in {"lead", "rhythm"}:
            if data.get("stem_role") != role or data.get("source_kind") != "role_specific_stem":
                raise StemSeparationError("Lead/Rhythm require an explicit role-specific stem contract")
            if output_hash == original_hash:
                raise StemSeparationError("A full-mix clone cannot qualify as a role-specific stem")
            other_role = "rhythm" if role == "lead" else "lead"
            other_stem = project / "stems" / f"{other_role}.wav"
            if other_stem.is_file() and sha256_file(other_stem) == output_hash:
                raise StemSeparationError("Lead/Rhythm stem bytes are identical across distinct roles")
    except (ValueError, TypeError, OSError) as exc:
        raise StemSeparationError("Malformed stem provenance receipt") from exc
    return stem
