"""Synthetic-only local resource telemetry for future bounded model pilots.

This runner NEVER accepts an arbitrary executable, a model path, media, script,
or command-line arguments. It runs one fixed Python stdlib memory workload to
verify the measurement/termination machinery before a licensed separator is
ever considered. Process working set is NOT a child-tree/GPU memory bound.
"""
from __future__ import annotations

import ctypes
from dataclasses import asdict, dataclass
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from typing import Callable

from .auto_cdlc_readiness import available_memory_gib


MiB = 1024 * 1024
SAMPLE_PERIOD_SECONDS = .025
# This workload has no I/O, network or model code. Its limited RAM pages are
# touched to make a predictable resident memory signal on common OSes.
_FIXED_WORKLOAD = """
import sys, time
megabytes = int(sys.argv[1])
hold_ms = int(sys.argv[2])
memory = bytearray(megabytes * 1024 * 1024)
for offset in range(0, len(memory), 4096):
    memory[offset] = 1
time.sleep(hold_ms / 1000.0)
assert len(memory) == megabytes * 1024 * 1024
"""


@dataclass(frozen=True)
class SyntheticResourceProbeResult:
    status: str
    elapsed_seconds: float
    peak_process_rss_mib: float | None
    sample_count: int
    minimum_observed_available_ram_gib: float | None
    process_ram_limit_mib: int
    synthetic_allocation_mib: int
    exit_code: int | None
    network_isolation_proven: bool = False
    model_execution_proven: bool = False
    separator_quality_proven: bool = False
    application_ready: bool = False

    def public_dict(self) -> dict:
        # Do not expose the host interpreter path, user directories,
        # subprocess error logs or private local source filenames.
        return asdict(self)


def _resident_rss_bytes(pid: int, process: subprocess.Popen) -> int | None:
    """Read only the probe process working set, never claim tree/GPU totals."""
    if sys.platform == "win32":
        from ctypes import wintypes

        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(counters)
        if not ctypes.windll.psapi.GetProcessMemoryInfo(
            ctypes.c_void_p(int(process._handle)),
            ctypes.byref(counters), ctypes.sizeof(counters)
        ):
            return None
        return int(counters.WorkingSetSize)

    if sys.platform.startswith("linux"):
        try:
            pages = int((Path("/proc") / str(pid) / "statm").read_text().split()[1])
            return pages * os.sysconf("SC_PAGE_SIZE")
        except (OSError, ValueError, IndexError):
            return None
    return None


def _stop_tree(process: subprocess.Popen) -> None:
    """Attempt to terminate the entire probe group; no unrelated PIDs."""
    if process.poll() is not None:
        return
    if sys.platform == "win32":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True, timeout=4, check=False,
            )
        except (subprocess.SubprocessError, OSError):
            pass
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (OSError, ProcessLookupError):
            pass
    if process.poll() is None:
        process.kill()


def run_synthetic_resource_probe(
    *,
    allocation_mib: int = 8,
    hold_ms: int = 350,
    process_limit_mib: int = 128,
    minimum_available_ram_gib: float = .5,
    available_probe: Callable[[], float] = available_memory_gib,
    resident_sampler: Callable[[int, subprocess.Popen], int | None] = _resident_rss_bytes,
) -> SyntheticResourceProbeResult:
    """Run only a fixed, bounded synthetic child and record real RSS samples.

    This cannot be used to execute a model. No claims about runtime isolation,
    GPU/RAM consumption of any external separator or actual transcription.
    """
    if type(allocation_mib) is not int or not 1 <= allocation_mib <= 64:
        raise ValueError("allocation_mib must be 1..64")
    if type(hold_ms) is not int or not 200 <= hold_ms <= 3000:
        raise ValueError("hold_ms must be 200..3000")
    if type(process_limit_mib) is not int or not 8 <= process_limit_mib <= 256:
        raise ValueError("process_limit_mib must be 8..256")
    if not math.isfinite(minimum_available_ram_gib) or not .25 <= minimum_available_ram_gib <= 16:
        raise ValueError("minimum_available_ram_gib must be 0.25..16")
    try:
        admitted = float(available_probe())
    except (OSError, ValueError, TypeError):
        admitted = float("nan")
    if not math.isfinite(admitted) or admitted < minimum_available_ram_gib:
        return SyntheticResourceProbeResult(
            "BLOCKED_PHYSICAL_RAM", 0.0, None, 0,
            round(admitted, 3) if math.isfinite(admitted) else None,
            process_limit_mib, allocation_mib, None,
        )

    kwargs = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL,
              "stderr": subprocess.DEVNULL}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    started = time.monotonic()
    process: subprocess.Popen | None = None
    peak: int | None = None
    samples = 0
    lowest_available = admitted
    exit_code = None
    status = "UNMEASURED"
    timeout_seconds = hold_ms / 1000.0 + 4.0
    try:
        process = subprocess.Popen([
            sys.executable, "-I", "-B", "-c",
            _FIXED_WORKLOAD, str(allocation_mib), str(hold_ms),
        ], **kwargs)
        while True:
            elapsed = time.monotonic() - started
            rss = resident_sampler(process.pid, process)
            if rss is not None and rss >= 0:
                peak = rss if peak is None else max(peak, rss)
                samples += 1
                if peak > process_limit_mib * MiB:
                    status = "PROCESS_RSS_LIMIT"
                    break
            if elapsed > timeout_seconds:
                status = "TIMEOUT"
                break
            if process.poll() is not None:
                exit_code = process.returncode
                status = (
                    "SYNTHETIC_ONLY_PASS" if exit_code == 0 and samples >= 2
                    else "UNMEASURED" if exit_code == 0 else "SYNTHETIC_CHILD_FAILED"
                )
                break
            try:
                available = float(available_probe())
                if not math.isfinite(available):
                    status = "RESOURCE_PROBE_FAILED"
                    break
                lowest_available = min(lowest_available, available)
                if available < minimum_available_ram_gib:
                    status = "HOST_PHYSICAL_RAM_FLOOR"
                    break
            except (OSError, ValueError, TypeError):
                status = "RESOURCE_PROBE_FAILED"
                break
            time.sleep(SAMPLE_PERIOD_SECONDS)
    except (OSError, subprocess.SubprocessError):
        status = "SYNTHETIC_CHILD_FAILED"
    finally:
        if process is not None:
            if process.poll() is None:
                _stop_tree(process)
            try:
                exit_code = process.wait(timeout=3)
            except (OSError, subprocess.TimeoutExpired):
                status = "UNCONFIRMED_CHILD_TERMINATION"
    return SyntheticResourceProbeResult(
        status=status,
        elapsed_seconds=round(time.monotonic() - started, 3),
        peak_process_rss_mib=round(peak / MiB, 3) if peak is not None else None,
        sample_count=samples,
        minimum_observed_available_ram_gib=round(lowest_available, 3),
        process_ram_limit_mib=process_limit_mib,
        synthetic_allocation_mib=allocation_mib,
        exit_code=exit_code,
    )
