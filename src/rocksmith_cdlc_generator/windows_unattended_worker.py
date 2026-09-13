from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys
from typing import Callable, Sequence

from .build_identity import current_build_identity

_TASK_NAME = "Rocksmith CDLC Unattended Worker"
_DISABLE_ENV = "ROCKSMITH_CDLC_DISABLE_UNATTENDED_WORKER"


@dataclass(frozen=True)
class WorkerRegistrationResult:
    supported: bool
    registered: bool
    changed: bool
    message: str


def source_checkout_root() -> Path:
    return Path(__file__).resolve().parents[2]


def worker_invocation() -> list[str]:
    """Build the command the Windows task should run without relying on a shell."""

    identity = current_build_identity()
    if identity.packaged:
        # The PyInstaller entry script handles this private switch before launching Tk.
        return [sys.executable, "--unattended-worker"]
    return [
        sys.executable,
        "-m",
        "rocksmith_cdlc_generator.unattended_worker_cli",
        "--repo-root",
        str(source_checkout_root()),
    ]


def _task_command(invocation: Sequence[str]) -> str:
    return subprocess.list2cmdline(list(invocation))


def registration_command(invocation: Sequence[str]) -> list[str]:
    """Create a current-user task that runs after ten minutes of machine idle time."""

    return [
        "schtasks.exe",
        "/Create",
        "/TN",
        _TASK_NAME,
        "/TR",
        _task_command(invocation),
        "/SC",
        "ONIDLE",
        "/I",
        "10",
        "/F",
    ]


def query_command() -> list[str]:
    return ["schtasks.exe", "/Query", "/TN", _TASK_NAME]


def ensure_windows_worker_registered(
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    os_name: str | None = None,
) -> WorkerRegistrationResult:
    """Idempotently register the private worker without blocking or prompting the user.

    Failure to register is deliberately non-fatal to the desktop application. The task
    performs read/diagnostic work only and runs under the current user after idle time.
    Set ROCKSMITH_CDLC_DISABLE_UNATTENDED_WORKER=1 to opt out on a machine where background
    execution is not desired.
    """

    current_os = os.name if os_name is None else os_name
    if current_os != "nt":
        return WorkerRegistrationResult(False, False, False, "Windows Task Scheduler is not applicable.")
    if os.environ.get(_DISABLE_ENV, "").strip().lower() in {"1", "true", "yes", "on"}:
        return WorkerRegistrationResult(True, False, False, "Unattended worker is disabled by environment setting.")

    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    common = {
        "check": False,
        "capture_output": True,
        "text": True,
        "timeout": 8,
        "creationflags": flags,
    }
    try:
        existing = runner(query_command(), **common)
    except (OSError, subprocess.SubprocessError) as exc:
        return WorkerRegistrationResult(True, False, False, f"Could not query Task Scheduler: {exc}")
    if existing.returncode == 0:
        return WorkerRegistrationResult(True, True, False, "Unattended idle worker is already registered.")

    try:
        created = runner(registration_command(worker_invocation()), **common)
    except (OSError, subprocess.SubprocessError) as exc:
        return WorkerRegistrationResult(True, False, False, f"Could not register unattended worker: {exc}")
    if created.returncode != 0:
        detail = (created.stderr or created.stdout or "Task Scheduler returned an error").strip()
        return WorkerRegistrationResult(True, False, False, f"Could not register unattended worker: {detail[:400]}")
    return WorkerRegistrationResult(
        True,
        True,
        True,
        "Registered unattended Product Reality worker to run after ten minutes of Windows idle time.",
    )
