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
    """Create/refresh a current-user task that runs after ten minutes of idle time."""

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


def deletion_command() -> list[str]:
    return ["schtasks.exe", "/Delete", "/TN", _TASK_NAME, "/F"]


def _run_task_command(
    runner: Callable[..., subprocess.CompletedProcess[str]],
    command: list[str],
) -> subprocess.CompletedProcess[str]:
    return runner(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=8,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def ensure_windows_worker_registered(
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    os_name: str | None = None,
) -> WorkerRegistrationResult:
    """Idempotently refresh or remove the private worker without prompting the user.

    Recreating the task with ``/F`` is intentional. Packaged builds may move when a new
    artifact replaces the old one; refreshing on every normal app launch prevents Task
    Scheduler from retaining an executable path that no longer exists.

    Setting ROCKSMITH_CDLC_DISABLE_UNATTENDED_WORKER=1 is a real opt-out: an existing task
    is deleted so a previously registered background worker cannot keep running. A missing
    task on the delete path is already equivalent to the requested disabled state.

    Registration/deletion failure is non-fatal to the desktop application and can be retried
    on a later launch. The worker itself performs read/diagnostic work only.
    """

    current_os = os.name if os_name is None else os_name
    if current_os != "nt":
        return WorkerRegistrationResult(False, False, False, "Windows Task Scheduler is not applicable.")

    disabled = os.environ.get(_DISABLE_ENV, "").strip().lower() in {"1", "true", "yes", "on"}
    if disabled:
        try:
            deleted = _run_task_command(runner, deletion_command())
        except (OSError, subprocess.SubprocessError) as exc:
            return WorkerRegistrationResult(
                True,
                False,
                False,
                f"Unattended worker is disabled, but Task Scheduler cleanup could not run: {exc}",
            )
        if deleted.returncode == 0:
            return WorkerRegistrationResult(
                True,
                False,
                True,
                "Unattended worker is disabled and the existing scheduled task was removed.",
            )
        # schtasks returns non-zero when the task does not exist; that already satisfies opt-out.
        return WorkerRegistrationResult(
            True,
            False,
            False,
            "Unattended worker is disabled and no active scheduled task was retained.",
        )

    try:
        created = _run_task_command(runner, registration_command(worker_invocation()))
    except (OSError, subprocess.SubprocessError) as exc:
        return WorkerRegistrationResult(True, False, False, f"Could not register unattended worker: {exc}")
    if created.returncode != 0:
        detail = (created.stderr or created.stdout or "Task Scheduler returned an error").strip()
        return WorkerRegistrationResult(True, False, False, f"Could not register unattended worker: {detail[:400]}")
    return WorkerRegistrationResult(
        True,
        True,
        True,
        "Registered/refreshed unattended Product Reality worker for the current build path.",
    )
