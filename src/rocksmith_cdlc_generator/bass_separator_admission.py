"""Fail-closed readiness gate for *optional* local Bass source separation.

Read-only preflight: never installs packages, searches private music, downloads
model weights, or launches a separator. Executing a cached local model is a
separate explicit user-authorized operation with its own resource gate.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import re
import shutil
import wave

from .auto_cdlc_readiness import available_memory_gib
from .hashing import sha256_file

MIN_AVAILABLE_RAM_GIB = 7.0
MIN_FREE_DISK_GIB = 8.0
MAX_PILOT_SECONDS = 45.0
_ALLOWED_MODEL_EXTENSIONS = frozenset({".onnx", ".pth", ".ckpt"})


@dataclass(frozen=True)
class BassSeparatorReadiness:
    status: str
    code: str
    available_ram_gib: float | None = None
    free_disk_gib: float | None = None
    model_sha256: str | None = None
    source_sha256: str | None = None
    input_seconds: float | None = None

    @property
    def admitted(self) -> bool:
        return self.status == "ADMITTED"

    def public_dict(self) -> dict:
        return {
            "status": self.status,
            "code": self.code,
            "available_ram_gib": self.available_ram_gib,
            "free_disk_gib": self.free_disk_gib,
            "model_sha256": self.model_sha256,
            "source_sha256": self.source_sha256,
            "input_seconds": self.input_seconds,
            "minimum_available_ram_gib": MIN_AVAILABLE_RAM_GIB,
            "minimum_free_disk_gib": MIN_FREE_DISK_GIB,
            "max_pilot_seconds": MAX_PILOT_SECONDS,
            "network_isolation_proven": False,
            "separator_model_quality_proven": False,
        }


def inspect_bass_separator_readiness(
    project_dir: Path,
    *,
    model_filename: str,
    model_file_dir: Path | None = None,
    expected_model_sha256: str | None = None,
    model_rights_confirmed: bool = False,
    memory_probe=None,
) -> BassSeparatorReadiness:
    """Inspect explicit model and local input with no execution or filesystem writes.

    A model basename + SHA proves only cache identity, NOT a license or a
    complete offline dependency graph. The external CLI might fetch configs,
    so runtime network isolation must be assessed independently.
    """
    if memory_probe is None:
        memory_probe = available_memory_gib
    project = Path(project_dir).resolve()
    source = (project / "audio" / "normalized.wav").resolve()
    def blocked(code: str, **details) -> BassSeparatorReadiness:
        return BassSeparatorReadiness("BLOCKED", code, **details)

    if not source.is_relative_to(project) or not source.is_file() or source.is_symlink():
        return blocked("NORMALIZED_AUDIO_MISSING")
    try:
        with wave.open(str(source), "rb") as audio:
            rate, channels, frames, width, compression = (
                audio.getframerate(), audio.getnchannels(), audio.getnframes(),
                audio.getsampwidth(), audio.getcomptype(),
            )
            if rate < 8000 or channels not in (1, 2) or width != 2 or compression != "NONE" or frames <= 0:
                return blocked("UNSUPPORTED_INPUT_PCM")
            seconds = frames / rate
            if seconds > MAX_PILOT_SECONDS:
                return blocked("FULL_SONG_EXECUTION_NOT_AUTHORIZED", input_seconds=round(seconds, 3))
            # The RIFF/data-chunk header can keep advertising the original frame
            # count after the file's actual PCM payload was truncated (crash,
            # full disk, partial copy). A file-size heuristic misses truncations
            # smaller than the header, so probe the real last declared frame
            # instead of trusting getnframes(), matching the same technique used
            # for stem output verification and the content-clock audit.
            audio.setpos(frames - 1)
            if len(audio.readframes(1)) != channels * width:
                return blocked("TRUNCATED_INPUT_PCM")
        source_hash = sha256_file(source)
    except (OSError, EOFError, ValueError, wave.Error):
        return blocked("INVALID_INPUT_AUDIO")

    details = {"source_sha256": source_hash, "input_seconds": round(seconds, 3)}
    if model_file_dir is None:
        return blocked("EXPLICIT_MODEL_CACHE_REQUIRED", **details)
    if (
        not model_filename
        or Path(model_filename).name != model_filename
        or model_filename in {".", ".."}
        or Path(model_filename).suffix.lower() not in _ALLOWED_MODEL_EXTENSIONS
        or any(separator in model_filename for separator in ("/", "\\", ":"))
    ):
        return blocked("INVALID_MODEL_FILENAME", **details)
    model_folder = Path(model_file_dir).resolve()
    model = model_folder / model_filename
    if not model_folder.is_dir() or not model.is_file() or model.is_symlink():
        return blocked("CACHED_MODEL_MISSING", **details)
    if not model.resolve().is_relative_to(model_folder):
        return blocked("MODEL_PATH_OUTSIDE_CACHE", **details)
    if not expected_model_sha256 or not re.fullmatch(r"[0-9a-f]{64}", expected_model_sha256):
        return blocked("MODEL_SHA256_PIN_REQUIRED", **details)
    try:
        if model.stat().st_size <= 0 or sha256_file(model) != expected_model_sha256:
            return blocked("CACHED_MODEL_HASH_MISMATCH", **details)
    except OSError:
        return blocked("CACHED_MODEL_UNREADABLE", **details)
    details["model_sha256"] = expected_model_sha256
    if not model_rights_confirmed:
        return blocked("MODEL_LICENSE_CONFIRMATION_REQUIRED", **details)
    if shutil.which("audio-separator") is None:
        return blocked("AUDIO_SEPARATOR_NOT_INSTALLED", **details)

    try:
        free_ram = memory_probe()
        free_disk = shutil.disk_usage(project).free / (1024 ** 3)
        if not all(math.isfinite(x) and x >= 0 for x in (free_ram, free_disk)):
            return blocked("RESOURCE_PROBE_INVALID", **details)
        details.update(
            available_ram_gib=round(free_ram, 3),
            free_disk_gib=round(free_disk, 3),
        )
    except (OSError, ValueError, TypeError):
        return blocked("RESOURCE_PROBE_UNAVAILABLE", **details)
    if free_ram < MIN_AVAILABLE_RAM_GIB:
        return blocked("INSUFFICIENT_AVAILABLE_PHYSICAL_RAM", **details)
    if free_disk < MIN_FREE_DISK_GIB:
        return blocked("INSUFFICIENT_FREE_DISK", **details)
    return BassSeparatorReadiness("ADMITTED", "LOCAL_PRECHECK_PASSED", **details)
