"""Read-only readiness evidence for upstream auto-cdlc and optional Wwise.

This module intentionally imports only Python's standard library. It never
installs packages, imports model libraries, loads model weights, runs Wwise,
downloads source code, touches Rocksmith or starts music generation.

The paths passed in are inspected, not discovered by scanning personal files.
"""
from __future__ import annotations

import ctypes
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

from .auto_cdlc_truth import KnownTruthError, verify_known_truth
from .hashing import sha256_file

REVIEWED_UPSTREAM_COMMIT = "cd7826f6a05a9acf8ff1825d52af9e2656d27d01"
BEAT_THIS_SHA256 = "8c328b45f59d8dd3dff219253ff6a8d6482be57d0133a29140e2febbf8eb8331"
MIN_FREE_RAM_GIB = 7.0
MIN_FREE_DISK_GIB = 8.0
_REQUIRED = {
    "numpy": ">=2",
    "scipy": ">=1.13",
    "librosa": ">=0.10",
    "soundfile": ">=0.12",
    "audioread": ">=3",
    "pretty_midi": ">=0.2.10",
    "PyGuitarPro": ">=0.9",
    "audio-separator": "==0.48.0",
    "madmom": "==0.17.dev0+puro",
    "mido": ">=1.2.6",
    "imageio-ffmpeg": ">=0.5",
    "mutagen": ">=1.47",
    "pillow": ">=10",
    "pyloudnorm": ">=0.1.1",
    "beat-this": "==1.1.0",
    "torchcrepe": "==0.0.24",
    "torch": "",
    "onnxruntime": "",
}
_VERSION_CHECK_SCRIPT = r'''
import importlib.metadata as md
import json
import sys
distributions = json.loads(sys.argv[1])
found = {}
for name in distributions:
    try:
        found[name] = md.version(name)
    except md.PackageNotFoundError:
        found[name] = None
print(json.dumps({
    "versions": found,
    "python": [sys.version_info.major, sys.version_info.minor],
    "isolated": sys.prefix != sys.base_prefix,
}, sort_keys=True))
'''


def available_memory_gib() -> float:
    """Available *physical* RAM; swap and total installed RAM are not admission."""
    if sys.platform == "win32":
        from ctypes import wintypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", wintypes.DWORD),
                ("dwMemoryLoad", wintypes.DWORD),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MEMORYSTATUSEX()
        status.dwLength = ctypes.sizeof(status)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            raise OSError("Cannot read Windows available physical RAM")
        return status.ullAvailPhys / (1024 ** 3)

    meminfo = Path("/proc/meminfo")
    if not meminfo.is_file():
        raise OSError("No supported available-physical-memory source")
    match = re.search(r"^MemAvailable:\s+(\d+)\s+kB", meminfo.read_text(), re.MULTILINE)
    if match is None:
        raise OSError("MemAvailable not reported")
    return int(match.group(1)) * 1024 / (1024 ** 3)


def _status(code: str, passed: bool, *, detail: dict | None = None) -> dict:
    entry = {"code": code, "passed": passed}
    if detail:
        entry["detail"] = detail
    return entry


def _minimum_satisfied(actual: str, requirement: str) -> bool:
    if not requirement:
        return True
    if requirement.startswith("=="):
        return actual.lower().replace("_", "-") == requirement[2:].lower().replace("_", "-")
    if not requirement.startswith(">="):
        return False
    minimum = requirement[2:]

    def numeric_prefix(value: str) -> tuple[int, ...] | None:
        match = re.fullmatch(r"(\d+(?:\.\d+)*)(?:\+[-\w.]+)?", value)
        if not match:
            return None  # refuse unknown prereleases and non-PEP-440 spellings
        return tuple(int(x) for x in match.group(1).split("."))

    actual_parts = numeric_prefix(actual)
    minimum_parts = numeric_prefix(minimum)
    if actual_parts is None or minimum_parts is None:
        return False
    width = max(len(actual_parts), len(minimum_parts))
    return (actual_parts + (0,) * (width - len(actual_parts))) >= (
        minimum_parts + (0,) * (width - len(minimum_parts))
    )


def _python_distributions(python: Path) -> dict:
    """Inspect metadata only, with no model import, pip invocation or download."""
    result = subprocess.run(
        [str(python), "-B", "-I", "-c", _VERSION_CHECK_SCRIPT, json.dumps(list(_REQUIRED))],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        check=False, timeout=18,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "HF_HUB_OFFLINE": "1",
             "TRANSFORMERS_OFFLINE": "1"},
    )
    if result.returncode != 0 or len(result.stdout) > 25000:
        raise ValueError("Python package metadata inspection failed")
    parsed = json.loads(result.stdout)
    if not isinstance(parsed, dict) or not isinstance(parsed.get("versions"), dict):
        raise ValueError("Python metadata response invalid")
    if parsed.get("python") != [3, 13]:
        raise ValueError("Runtime is not Python 3.13")
    return parsed


def _git_checkout(path: Path) -> dict:
    if not path.is_dir() or not (path / ".git").exists() or not (path / "cdlc_bajo.py").is_file():
        raise ValueError("Pinned upstream checkout not found")
    head = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True, timeout=10,
    ).stdout.strip()
    if head != REVIEWED_UPSTREAM_COMMIT:
        raise ValueError("Upstream Git HEAD differs from reviewed commit")
    dirty = subprocess.run(
        ["git", "-C", str(path), "status", "--porcelain", "--untracked-files=no"],
        capture_output=True, text=True, check=True, timeout=10,
    ).stdout
    if dirty.strip():
        raise ValueError("Upstream tracked files changed")
    return {"reviewed_commit": head, "script_sha256": sha256_file(path / "cdlc_bajo.py")}


def _cache_checks(checkout: Path) -> list[dict]:
    checks = []
    models = checkout / "modelos"
    bass = models / "kuielab_b_bass.onnx"
    if bass.is_file() and not bass.is_symlink() and bass.stat().st_size > 1024 * 1024:
        checks.append(_status("BASS_ONNX_MODEL_CACHED", True,
                              detail={"model_sha256": sha256_file(bass), "expected_hash_known": False}))
    else:
        checks.append(_status("BASS_ONNX_MODEL_CACHED", False))
    beat = models / "beat_this-final0.ckpt"
    if (beat.is_file() and not beat.is_symlink() and beat.stat().st_size >= 50_000_000
            and sha256_file(beat) == BEAT_THIS_SHA256):
        checks.append(_status("BEAT_THIS_CHECKPOINT_PINNED", True,
                              detail={"sha256": BEAT_THIS_SHA256}))
    else:
        checks.append(_status("BEAT_THIS_CHECKPOINT_PINNED", False))
    return checks


def _wwise_candidate(explicit: Path | None) -> bool:
    options: list[Path] = []
    if explicit:
        options.append(explicit)
    root = os.environ.get("WWISEROOT")
    if root:
        options.append(Path(root))
    for key in ("ProgramFiles", "ProgramFiles(x86)"):
        parent = os.environ.get(key)
        if parent:
            audio = Path(parent) / "Audiokinetic"
            if audio.is_dir():
                options.extend(sorted(audio.glob("Wwise*")))
    for candidate in options:
        if candidate.name.lower() == "wwiseconsole.exe" and candidate.is_file():
            return True
        if (candidate / "Authoring" / "x64" / "Release" / "bin" / "WwiseConsole.exe").is_file():
            return True
    return False


def inspect_upstream_readiness(
    *,
    fixture_dir: Path | None = None,
    upstream_checkout: Path | None = None,
    python_313_exe: Path | None = None,
    run_parent: Path | None = None,
    wwise_console: Path | None = None,
) -> dict:
    """Inspect local prerequisites only; no folder creation or model execution.

    The resulting JSON does not include personal paths, song data, or raw logs.
    A checked package or cache presence is not a real transcription result.
    """
    checks: list[dict] = []
    advisories: list[str] = []
    hashes: dict[str, str] = {}

    try:
        free_ram = available_memory_gib()
        checks.append(_status("PHYSICAL_RAM_AT_LEAST_7_GIB", free_ram >= MIN_FREE_RAM_GIB,
                              detail={"available_gib": round(free_ram, 3)}))
    except (OSError, ValueError):
        checks.append(_status("PHYSICAL_RAM_AT_LEAST_7_GIB", False))
    disk_root = Path(run_parent).expanduser().resolve() if run_parent is not None else Path.cwd()
    try:
        free_disk = shutil.disk_usage(disk_root).free / (1024 ** 3)
        checks.append(_status("RUN_VOLUME_FREE_DISK_AT_LEAST_8_GIB",
                              free_disk >= MIN_FREE_DISK_GIB,
                              detail={"available_gib": round(free_disk, 3)}))
    except (OSError, ValueError):
        checks.append(_status("RUN_VOLUME_FREE_DISK_AT_LEAST_8_GIB", False))

    if fixture_dir is None:
        checks.append(_status("SYNTHETIC_FIXTURE_VERIFIED", False))
    else:
        try:
            _wav, truth = verify_known_truth(Path(fixture_dir))
            hashes["synthetic_audio"] = str(truth["source_audio_sha256"])
            checks.append(_status("SYNTHETIC_FIXTURE_VERIFIED", True))
        except (OSError, KnownTruthError, ValueError):
            checks.append(_status("SYNTHETIC_FIXTURE_VERIFIED", False))

    if upstream_checkout is None:
        checks.extend([
            _status("UPSTREAM_REVIEWED_CHECKOUT", False),
            _status("BASS_ONNX_MODEL_CACHED", False),
            _status("BEAT_THIS_CHECKPOINT_PINNED", False),
        ])
    else:
        checkout = Path(upstream_checkout).expanduser().resolve()
        try:
            source_info = _git_checkout(checkout)
            hashes["upstream_script"] = source_info["script_sha256"]
            checks.append(_status("UPSTREAM_REVIEWED_CHECKOUT", True))
            checks.extend(_cache_checks(checkout))
        except (OSError, ValueError, subprocess.SubprocessError):
            checks.extend([
                _status("UPSTREAM_REVIEWED_CHECKOUT", False),
                _status("BASS_ONNX_MODEL_CACHED", False),
                _status("BEAT_THIS_CHECKPOINT_PINNED", False),
            ])

    if python_313_exe is None:
        checks.append(_status("PYTHON_313_PACKAGE_SET", False))
    else:
        python = Path(python_313_exe).expanduser().absolute()
        try:
            metadata = _python_distributions(python)
            missing = [
                name for name, requirement in _REQUIRED.items()
                if not isinstance(metadata["versions"].get(name), str)
                or not _minimum_satisfied(metadata["versions"][name], requirement)
            ]
            checks.append(_status("PYTHON_313_PACKAGE_SET", not missing,
                                  detail={"unmet_packages": missing,
                                          "installed_count": len(_REQUIRED) - len(missing),
                                          "required_count": len(_REQUIRED)}))
            if not metadata.get("isolated"):
                advisories.append("PYTHON_INTERPRETER_NOT_IN_VIRTUALENV")
            hashes["python_executable"] = sha256_file(python)
        except (OSError, ValueError, json.JSONDecodeError, subprocess.SubprocessError):
            checks.append(_status("PYTHON_313_PACKAGE_SET", False))

    wwise_visible = _wwise_candidate(Path(wwise_console) if wwise_console else None)
    # Wwise is *not required* for the synthetic audio transcription lane.
    # Visibility does not prove conversion, version compatibility or WEM.
    checks.append(_status("WWISE_CONSOLE_LOCATED", wwise_visible))
    synthetic_required = [check for check in checks if check["code"] != "WWISE_CONSOLE_LOCATED"]
    missing_codes = [check["code"] for check in synthetic_required if not check["passed"]]
    return {
        "schema_version": 1,
        "kind": "auto_cdlc_local_readiness_v1",
        "recorded_utc": datetime.now(timezone.utc).isoformat(),
        "reviewed_commit": REVIEWED_UPSTREAM_COMMIT,
        "synthetic_transcription_ready": not missing_codes,
        "synthetic_blocker_codes": missing_codes,
        "wwise_console_located": wwise_visible,
        "wwise_packaging_verified": False,
        "real_song_accuracy_verified": False,
        "real_rocksmith_gameplay_verified": False,
        "network_isolation_proven": False,
        "model_producer_provenance_verified": False,
        "checks": checks,
        "advisories": advisories,
        "sha256": hashes,
    }
