"""Low-impact, unattended *scheduled* worker admission on Windows.

Windows Task Scheduler's ONIDLE trigger can remain queued indefinitely on an
already-idle laptop. A periodic time trigger invokes this tiny, fail-closed
gate; actual Product Reality work runs only with verified owner absence,
reasonable system CPU load, AC power and no active Rocksmith session.

The separate --unattended-worker entrypoint remains an explicit diagnostic.
No model, game, GUI, music, or project files are touched by a skipped check.
"""
from __future__ import annotations

import csv
import ctypes
from ctypes import wintypes
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

_IDLE_FLOOR_SECONDS = 600.0
_CPU_MAX_PERCENT = 20.0
_LIVE_GAME_IMAGES = frozenset({
    "rocksmith2014.exe", "rocksmith.exe", "nocablelauncher.exe"
})
_DISABLE_ENV = "ROCKSMITH_CDLC_DISABLE_UNATTENDED_WORKER"


@dataclass(frozen=True)
class SchedulerAdmission:
    on_ac: bool
    active_console: bool
    idle_seconds: float
    cpu_busy_percent: float
    music_game_running: bool


def decide_admission(probe: SchedulerAdmission) -> str:
    """Pure policy with stable privacy-safe reason codes, no overrides."""
    if not probe.on_ac:
        return "NOT_ON_AC"
    if not probe.active_console:
        return "NO_ACTIVE_CONSOLE"
    if not math.isfinite(probe.idle_seconds) or probe.idle_seconds < _IDLE_FLOOR_SECONDS:
        return "USER_RECENTLY_ACTIVE"
    if not math.isfinite(probe.cpu_busy_percent) or not 0 <= probe.cpu_busy_percent <= _CPU_MAX_PERCENT:
        return "CPU_BUSY_OR_UNKNOWN"
    if probe.music_game_running:
        return "ROCKSMITH_RUNNING"
    return "ADMITTED"


class _LastInputInfo(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


class _SystemPowerStatus(ctypes.Structure):
    _fields_ = [
        ("ACLineStatus", ctypes.c_byte),
        ("BatteryFlag", ctypes.c_byte),
        ("BatteryLifePercent", ctypes.c_byte),
        ("SystemStatusFlag", ctypes.c_byte),
        ("BatteryLifeTime", wintypes.DWORD),
        ("BatteryFullLifeTime", wintypes.DWORD),
    ]


class _FileTime(ctypes.Structure):
    _fields_ = [("low", wintypes.DWORD), ("high", wintypes.DWORD)]


def _filetime_number(value: _FileTime) -> int:
    return (value.high << 32) | value.low


def _windows_user_idle_seconds() -> float:
    info = _LastInputInfo()
    info.cbSize = ctypes.sizeof(info)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
        raise OSError("Could not read last interactive input")
    # GetLastInputInfo is per-session and dwTime wraps at 32 bits.
    get_tick = ctypes.windll.kernel32.GetTickCount64
    get_tick.restype = ctypes.c_ulonglong
    now = int(get_tick()) & 0xFFFFFFFF
    elapsed = (now - int(info.dwTime)) & 0xFFFFFFFF
    return elapsed / 1000.0


def _on_ac_power() -> bool:
    status = _SystemPowerStatus()
    if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):
        raise OSError("Cannot read Windows AC power status")
    return status.ACLineStatus == 1


def _has_active_console() -> bool:
    kernel32 = ctypes.windll.kernel32
    kernel32.WTSGetActiveConsoleSessionId.restype = wintypes.DWORD
    active = kernel32.WTSGetActiveConsoleSessionId()
    current = wintypes.DWORD()
    if active == 0xFFFFFFFF:
        return False
    if not kernel32.ProcessIdToSessionId(os.getpid(), ctypes.byref(current)):
        raise OSError("Could not inspect worker session")
    return int(active) == int(current.value)


def _system_cpu_percent() -> float:
    kernel32 = ctypes.windll.kernel32

    def snapshot() -> tuple[int, int, int]:
        idle, kernel, user = _FileTime(), _FileTime(), _FileTime()
        if not kernel32.GetSystemTimes(
            ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)
        ):
            raise OSError("Could not read CPU utilization")
        return tuple(_filetime_number(x) for x in (idle, kernel, user))

    before = snapshot()
    time.sleep(0.4)
    after = snapshot()
    idle_delta, kernel_delta, user_delta = (
        a - b for a, b in zip(after, before)
    )
    total = kernel_delta + user_delta
    if total <= 0 or idle_delta < 0 or idle_delta > total:
        raise OSError("Invalid sampled CPU counter")
    return max(0.0, min(100.0, 100.0 * (total - idle_delta) / total))


def _rocksmith_running() -> bool:
    command = ["tasklist.exe", "/FO", "CSV", "/NH"]
    completed = subprocess.run(
        command, capture_output=True, text=True, timeout=10,
        check=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if completed.returncode:
        raise OSError("Cannot inspect running game processes")
    for row in csv.reader(completed.stdout.splitlines()):
        if row and row[0].strip().casefold() in _LIVE_GAME_IMAGES:
            return True
    return False


def read_admission() -> SchedulerAdmission:
    if sys.platform != "win32":
        raise OSError("Scheduled worker admission requires Windows")
    return SchedulerAdmission(
        on_ac=_on_ac_power(),
        active_console=_has_active_console(),
        idle_seconds=_windows_user_idle_seconds(),
        cpu_busy_percent=_system_cpu_percent(),
        music_game_running=_rocksmith_running(),
    )


def _write_local_gate_report(status: str, reason: str) -> None:
    """Atomic status heartbeat, intentionally omitting paths and process names."""
    from .build_identity import current_build_identity

    base = os.environ.get("LOCALAPPDATA")
    if not base:
        return
    root = Path(base) / "RocksmithCDLCGenerator" / "unattended-worker"
    root.mkdir(parents=True, exist_ok=True)
    destination = root / "scheduler_gate.json"
    temporary = root / ("scheduler_gate." + uuid.uuid4().hex + ".tmp")
    payload = {
        "schema_version": 1,
        "observed_utc": datetime.now(timezone.utc).isoformat(),
        "build_sha": current_build_identity().commit_sha,
        "status": status,
        "reason_code": reason,
    }
    try:
        temporary.write_text(json.dumps(payload, allow_nan=False) + "\n", encoding="utf-8")
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    if os.environ.get(_DISABLE_ENV, "").strip().casefold() in {
        "1", "true", "yes", "on"
    }:
        _write_local_gate_report("SKIPPED", "OWNER_DISABLED")
        return 0
    try:
        probe = read_admission()
        reason = decide_admission(probe)
    except (OSError, ValueError, subprocess.SubprocessError, RuntimeError):
        reason = "METRICS_UNAVAILABLE"
    if reason != "ADMITTED":
        _write_local_gate_report("SKIPPED", reason)
        return 0

    # The scheduled route uses the *existing* lock-protected worker,
    # authority boundaries, local evidence ledger and privacy controls.
    from .unattended_worker_cli import main as run_local_worker

    _write_local_gate_report("STARTED", "ADMITTED")
    try:
        code = run_local_worker(argv)
    except Exception as exc:
        _write_local_gate_report("FAILED", type(exc).__name__)
        return 1
    _write_local_gate_report("COMPLETED" if code == 0 else "FAILED",
                             "WORKER_EXIT_ZERO" if code == 0 else "WORKER_EXIT_NONZERO")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
