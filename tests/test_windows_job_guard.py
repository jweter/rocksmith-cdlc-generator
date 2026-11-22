"""Actual Windows Job Object tests, no model or network dependency."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from pathlib import Path
import subprocess
import sys
import time

import pytest

from rocksmith_cdlc_generator.windows_job_guard import (
    start_windows_job_child, WAIT_OBJECT_0,
)


pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows Job Object API required")


def test_guarded_python_child_starts_suspended_attached_and_completes():
    child = start_windows_job_child([
        sys.executable, "-I", "-B", "-c", "import time;time.sleep(.2)",
    ], job_limit_bytes=128 * 1024**2, active_process_limit=2)
    try:
        assert child.pid > 0
        assert child.wait(timeout=4) == 0
        assert child.configured_job_limit_bytes() == 128 * 1024**2
        assert child.peak_job_commit_bytes() is not None
        assert child.peak_job_commit_bytes() > 0
    finally:
        child.close()


def test_real_kernel_job_memory_limit_blocks_overbudget_child(tmp_path: Path):
    sentinel = tmp_path / "allocation-success-sentinel.txt"
    script = (
        "import pathlib,time;"
        "x=bytearray(128*1024*1024);"
        "pathlib.Path(sys.argv[1]).write_text('unbounded',encoding='utf-8');"
        "time.sleep(.1)"
    )
    # A command-line Python script uses sys.argv, import it explicitly.
    script = "import sys;" + script
    child = start_windows_job_child([
        sys.executable, "-I", "-B", "-c", script, str(sentinel),
    ], job_limit_bytes=32 * 1024**2, active_process_limit=2)
    try:
        assert child.configured_job_limit_bytes() == 32 * 1024**2
        status = child.wait(timeout=8)
        assert status != 0, "An over-limit allocation must not complete successfully"
        assert not sentinel.exists(), "Job memory cap must prevent a 128MiB allocation"
        assert child.peak_job_commit_bytes() is not None
        # Windows PeakJobMemoryUsed can include the allocation-failure
        # high-water observation; it is a diagnostic, NOT the configured
        # enforced limit. The exact JobMemoryLimit is independently read back.
    finally:
        child.close()


def test_kill_on_job_close_terminates_grandchild_not_just_parent(tmp_path: Path):
    # The only test child is a short original Python script which itself
    # launches one short-lived Python sleeper. No arbitrary user command,
    # commercial music, external model or network is involved.
    pid_file = tmp_path / "grandchild-pid.txt"
    script = (
        "import subprocess,sys,time,pathlib;"
        "p=subprocess.Popen([sys.executable,'-I','-B','-c','import time;time.sleep(15)']);"
        "pathlib.Path(sys.argv[1]).write_text(str(p.pid),encoding='utf-8');"
        "time.sleep(15)"
    )
    child = start_windows_job_child([
        sys.executable, "-I", "-B", "-c", script, str(pid_file),
    ], job_limit_bytes=128 * 1024**2, active_process_limit=3)
    grandchild_pid = None
    try:
        deadline = time.monotonic() + 6
        while time.monotonic() < deadline and not pid_file.is_file():
            if child.poll() is not None:
                break
            time.sleep(.05)
        assert pid_file.is_file(), "Parent should create exactly one nested child"
        grandchild_pid = int(pid_file.read_text(encoding="utf-8"))
        assert grandchild_pid > 0
        child.kill()
        assert child.wait(timeout=5) != 0
    finally:
        child.close()

    # The grandchild inherits the job, and closing it must kill every
    # attached process even if the parent already terminated.
    dll = ctypes.WinDLL("kernel32", use_last_error=True)
    dll.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    dll.OpenProcess.restype = wintypes.HANDLE
    dll.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    dll.WaitForSingleObject.restype = wintypes.DWORD
    dll.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = dll.OpenProcess(0x00100000, False, grandchild_pid)
    if handle:
        try:
            assert dll.WaitForSingleObject(handle, 2000) == WAIT_OBJECT_0
        finally:
            dll.CloseHandle(handle)
    # If the PID cannot be opened, it has already been reaped, which also
    # satisfies containment. A recycled PID in this short interval is unlikely.


@pytest.mark.parametrize("memory,processes", [(0, 2), (4 * 1024**2, 2), (128 * 1024**2, 0), (128 * 1024**2, 10)])
def test_out_of_bounds_kernel_job_limits_are_rejected(memory, processes):
    with pytest.raises(ValueError):
        start_windows_job_child([sys.executable, "-I", "-B", "-c", "pass"],
                                job_limit_bytes=memory, active_process_limit=processes)


def test_live_job_tree_rss_includes_grandchild_not_just_main_process():
    # Known bounded Python-only fixture; no model, music, network or GPU.
    # A grandchild allocates 18 MiB to distinguish job-total RSS from parent RSS.
    script = (
        "import subprocess,sys,time;"
        "subprocess.Popen([sys.executable,'-I','-B','-c',"
        "'import time;x=bytearray(18*1024*1024);time.sleep(2)']);"
        "time.sleep(2)"
    )
    child = start_windows_job_child(
        [sys.executable, "-I", "-B", "-c", script],
        job_limit_bytes=128 * 1024**2, active_process_limit=3,
    )
    from rocksmith_cdlc_generator.synthetic_resource_probe import _resident_rss_bytes
    try:
        deadline = time.monotonic() + 6
        proved_two = False
        while time.monotonic() < deadline:
            count = child.current_tree_process_count()
            if count is not None and count >= 2:
                aggregate = child.current_tree_working_set_bytes()
                direct = _resident_rss_bytes(child.pid, child)
                if aggregate is not None and direct is not None:
                    assert aggregate >= direct + 8 * 1024**2
                    proved_two = True
                    break
            time.sleep(.05)
        assert proved_two, "Windows Job Object must capture grandchild RSS"
    finally:
        if child.poll() is None:
            child.kill()
        child.close()


def test_closed_job_never_claims_new_tree_snapshot():
    child = start_windows_job_child(
        [sys.executable, "-I", "-B", "-c", "pass"],
        job_limit_bytes=64 * 1024**2, active_process_limit=2,
    )
    child.wait(timeout=4)
    child.close()
    assert child.current_tree_process_count() is None
    assert child.current_tree_working_set_bytes() is None
