"""Opt-in local-only executor for the pinned upstream auto-cdlc on original test audio.

This adapter never downloads/install models or touches real songs/the game.
It runs ONLY the reproducible original synthetic fixture so that even a
third-party executable's unexpected network behavior cannot expose music.
'--sin-internet' disables upstream metadata/updater/telemetry features, but
does NOT promise OS-level network isolation: model caches need preparation.
"""
from __future__ import annotations

import ctypes
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

from .auto_cdlc_truth import KnownTruthError, PROFILE, verify_known_truth
from .auto_cdlc_truth_benchmark import run_known_truth_benchmark
from .corpus_differential_harness import refuse_output_inside_repository_checkout
from .hashing import sha256_file

_REVIEWED_COMMIT = "cd7826f6a05a9acf8ff1825d52af9e2656d27d01"
_MIN_MEMORY_GIB = 7.0
_MIN_DISK_GIB = 8.0
_MAX_RUN_SECONDS = 7200
_SUPPORTED_PYTHON = "Python 3.13"
_EVIDENCE_NAME = "upstream_run_evidence.json"


class UpstreamRunError(ValueError):
    """Refused external execution or missing/nonpassing upstream evidence."""


def _available_memory_gib() -> float:
    if sys.platform == "win32":
        from ctypes import wintypes

        class _MemoryStatus(ctypes.Structure):
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

        info = _MemoryStatus()
        info.dwLength = ctypes.sizeof(info)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(info)):
            raise UpstreamRunError("Unable to read Windows available physical memory")
        return info.ullAvailPhys / (1024 ** 3)

    meminfo = Path("/proc/meminfo")
    if not meminfo.is_file():
        raise UpstreamRunError("Cannot measure available RAM for external model admission")
    match = re.search(r"^MemAvailable:\s+(\d+)\s+kB", meminfo.read_text(), re.MULTILINE)
    if not match:
        raise UpstreamRunError("MemAvailable is missing")
    return int(match.group(1)) * 1024 / (1024 ** 3)


def _pinned_checkout(path: Path) -> tuple[str, Path]:
    script = path / "cdlc_bajo.py"
    if not script.is_file() or not (path / ".git").exists():
        raise UpstreamRunError("Expected upstream Git checkout with cdlc_bajo.py")
    try:
        head = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True, timeout=8,
        ).stdout.strip()
        changes = subprocess.run(
            ["git", "-C", str(path), "status", "--porcelain", "--untracked-files=no"],
            capture_output=True, text=True, check=True, timeout=8,
        ).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        raise UpstreamRunError("Cannot inspect upstream source revision") from exc
    if head != _REVIEWED_COMMIT:
        raise UpstreamRunError("Upstream checkout must be at the explicitly reviewed commit")
    if changes.strip():
        raise UpstreamRunError("Upstream checkout has modified tracked source files")
    return sha256_file(script), script


def _python_313(path: Path) -> str:
    if not path.is_file():
        raise UpstreamRunError("Python 3.13 executable not found")
    try:
        result = subprocess.run(
            [str(path), "--version"], capture_output=True, text=True,
            check=True, timeout=8,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise UpstreamRunError("Cannot verify the external Python interpreter") from exc
    reported = (result.stdout + result.stderr).strip()
    if not re.fullmatch(r"Python 3\.13(?:\.\d+)?", reported):
        raise UpstreamRunError("Upstream requires an isolated Python 3.13 interpreter")
    return sha256_file(path)


def _upstream_output_root(root: Path) -> Path:
    candidates = sorted(
        p.parent for p in root.rglob("diagnostico.json")
        if p.is_file() and p.parent != root
    )
    if len(candidates) != 1:
        raise UpstreamRunError(
            f"Expected exactly one generated upstream diagnostico.json; found {len(candidates)}"
        )
    selected = candidates[0].resolve()
    if not selected.is_relative_to(root.resolve()):
        raise UpstreamRunError("Generated artifacts escaped local output sandbox")
    if len(list(selected.glob("*.mid"))) != 1 or len(list(selected.glob("*.svl"))) != 1:
        raise UpstreamRunError("Upstream did not produce one matching MIDI and SVL artifact")
    return selected


def _safe_output_root(
    root: Path, *, fixture: Path, checkout: Path, python: Path
) -> None:
    refuse_output_inside_repository_checkout(root / _EVIDENCE_NAME)
    if root.exists():
        raise UpstreamRunError("Private run directory must not already exist")
    if root.is_relative_to(fixture) or fixture.is_relative_to(root):
        raise UpstreamRunError("Run directory must not overlap known-truth fixture")
    if root.is_relative_to(checkout) or checkout.is_relative_to(root):
        raise UpstreamRunError("Run directory must not overlap upstream source checkout")
    if python.is_relative_to(root):
        raise UpstreamRunError("Run directory must not include Python interpreter")
    if not root.parent.is_dir():
        raise UpstreamRunError("Create the run directory parent before execution")
    if shutil.disk_usage(root.parent).free / (1024 ** 3) < _MIN_DISK_GIB:
        raise UpstreamRunError("Insufficient free disk space for isolated model execution")


def run_pinned_upstream_synthetic(
    fixture_dir: Path,
    *,
    upstream_checkout: Path,
    python_313_exe: Path,
    run_dir: Path,
    confirm_noncommercial: bool = False,
    timeout_seconds: int = 3600,
) -> dict[str, object]:
    """Run a third-party model only against original synthesized audio.

    Prerequisites (Python model env, cached audio models, source checkout)
    are provisioned externally. Never downloads models or installs Wwise.
    A run is intentionally denied when memory admission fails; to avoid
    starving the owner's active autonomous agent no override exists.
    """
    if not confirm_noncommercial:
        raise UpstreamRunError("Owner must explicitly approve noncommercial model use")
    if not 1 <= timeout_seconds <= _MAX_RUN_SECONDS:
        raise UpstreamRunError("Timeout must be in the range 1..7200 seconds")
    fixture = fixture_dir.expanduser().resolve()
    checkout = upstream_checkout.expanduser().resolve()
    # A virtualenv's bin/python is commonly a symlink to the base binary.
    # Resolve for fingerprinting only: *execute* the explicitly selected venv
    # entry point so its site-packages and interpreter prefix remain active.
    python = python_313_exe.expanduser().absolute()
    destination = run_dir.expanduser().resolve()
    _safe_output_root(destination, fixture=fixture, checkout=checkout, python=python)
    wav, truth = verify_known_truth(fixture)
    source_script_hash, script = _pinned_checkout(checkout)
    interpreter_sha256 = _python_313(python)
    free_ram = _available_memory_gib()
    if free_ram < _MIN_MEMORY_GIB:
        raise UpstreamRunError(
            f"Model admission refused: available RAM {free_ram:.2f} GiB "
            f"below {_MIN_MEMORY_GIB:.1f} GiB safety floor"
        )

    # All source inputs and toolchain are now pinned; no run directory was
    # created before the admission/owner-rights preflight.
    destination.mkdir(parents=True, exist_ok=False)
    upstream_out = destination / "upstream"
    upstream_out.mkdir()
    run_log = destination / _EVIDENCE_NAME
    report: dict[str, object] = {
        "schema_version": 1,
        "kind": "pinned_auto_cdlc_synthetic_execution_v1",
        "recorded_utc": datetime.now(timezone.utc).isoformat(),
        "status": "FAIL",
        "source_audio_sha256": truth["source_audio_sha256"],
        "fixture_profile": PROFILE,
        "upstream_commit": _REVIEWED_COMMIT,
        "upstream_script_sha256": source_script_hash,
        "python_313_sha256": interpreter_sha256,
        "available_ram_gib_at_start": round(free_ram, 3),
        "noncommercial_use_confirmed": True,
        "os_level_network_isolation": "NOT_PROVEN",
        "game_installation_changed": False,
        "return_code": None,
    }
    try:
        command = [
            str(python), str(script), str(wav),
            "--salida", str(upstream_out),
            "--sin-internet", "--sin-actualizar", "--sin-psarc", "--sin-preguntas",
        ]
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        environment["HF_HUB_OFFLINE"] = "1"
        environment["TRANSFORMERS_OFFLINE"] = "1"
        try:
            completed = subprocess.run(
                command,
                cwd=checkout, env=environment, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise UpstreamRunError("Pinned external model exceeded bounded runtime") from exc
        report["return_code"] = completed.returncode
        # Logs from a synthetic run may be retained only under the owner
        # private out directory, never in Git/automated PR comments.
        report["stdout_tail"] = completed.stdout[-12000:]
        report["stderr_tail"] = completed.stderr[-12000:]
        if completed.returncode:
            raise UpstreamRunError(f"Upstream process failed with exit code {completed.returncode}")
        if sha256_file(wav) != truth["source_audio_sha256"]:
            raise UpstreamRunError("Original synthetic audio changed during execution")
        generated = _upstream_output_root(upstream_out)
        benchmark_path = destination / "benchmark.json"
        result = run_known_truth_benchmark(
            fixture, upstream_dir=generated, out_path=benchmark_path,
        )
        report["generated_midi_sha256"] = sha256_file(next(generated.glob("*.mid")))
        report["generated_svl_sha256"] = sha256_file(next(generated.glob("*.svl")))
        report["generated_diagnostic_sha256"] = sha256_file(generated / "diagnostico.json")
        report["synthetic_verdict"] = result["comparison_verdict"]
        report["status"] = "PASS" if result["comparison_verdict"] == "PASS" else "BENCHMARK_FAIL"
        return report
    except Exception as exc:
        report["error_class"] = type(exc).__name__
        raise
    finally:
        run_log.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
