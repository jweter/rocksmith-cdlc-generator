"""Windows Job Object containment for the fixed synthetic resource probe only.

Spawns the fixed Python child SUSPENDED, attaches it to a job with an
OS-enforced aggregate committed-memory limit and active process count,
then resumes. This is NOT a network sandbox, GPU budget or authority to
launch an arbitrary AI model.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import subprocess
import sys


JOB_OBJECT_BASIC_PROCESS_ID_LIST_CLASS = 3
JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS = 9
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
MAX_JOB_PIDS = 8
JOB_OBJECT_LIMIT_ACTIVE_PROCESS = 0x00000008
JOB_OBJECT_LIMIT_JOB_MEMORY = 0x00000200
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
CREATE_SUSPENDED = 0x00000004
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_NO_WINDOW = 0x08000000
WAIT_OBJECT_0 = 0
WAIT_TIMEOUT = 258
INVALID_RESUME_THREAD_RESULT = 0xFFFFFFFF


class _BasicLimit(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class _IoCounters(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_ulonglong),
        ("WriteOperationCount", ctypes.c_ulonglong),
        ("OtherOperationCount", ctypes.c_ulonglong),
        ("ReadTransferCount", ctypes.c_ulonglong),
        ("WriteTransferCount", ctypes.c_ulonglong),
        ("OtherTransferCount", ctypes.c_ulonglong),
    ]


class _ExtendedLimits(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _BasicLimit),
        ("IoInfo", _IoCounters),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


class _JobProcessIds(ctypes.Structure):
    # Windows JOBOBJECT_BASIC_PROCESS_ID_LIST contains a variable-length
    # ULONG_PTR array. The synthetic job permits at most three active
    # processes; eight slots provide bounded headroom for snapshots.
    _fields_ = [
        ("NumberOfAssignedProcesses", wintypes.DWORD),
        ("NumberOfProcessIdsInList", wintypes.DWORD),
        ("ProcessIdList", ctypes.c_size_t * MAX_JOB_PIDS),
    ]


class _ProcessMemoryCounters(ctypes.Structure):
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


class _StartupInfo(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("lpReserved", wintypes.LPWSTR),
        ("lpDesktop", wintypes.LPWSTR),
        ("lpTitle", wintypes.LPWSTR),
        ("dwX", wintypes.DWORD),
        ("dwY", wintypes.DWORD),
        ("dwXSize", wintypes.DWORD),
        ("dwYSize", wintypes.DWORD),
        ("dwXCountChars", wintypes.DWORD),
        ("dwYCountChars", wintypes.DWORD),
        ("dwFillAttribute", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("wShowWindow", wintypes.WORD),
        ("cbReserved2", wintypes.WORD),
        ("lpReserved2", ctypes.POINTER(ctypes.c_ubyte)),
        ("hStdInput", wintypes.HANDLE),
        ("hStdOutput", wintypes.HANDLE),
        ("hStdError", wintypes.HANDLE),
    ]


class _ProcessInfo(ctypes.Structure):
    _fields_ = [
        ("hProcess", wintypes.HANDLE),
        ("hThread", wintypes.HANDLE),
        ("dwProcessId", wintypes.DWORD),
        ("dwThreadId", wintypes.DWORD),
    ]


def _api():
    if sys.platform != "win32":
        raise OSError("WINDOWS_JOB_OBJECT_UNAVAILABLE")
    dll = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = wintypes.HANDLE
    dll.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    dll.CreateJobObjectW.restype = handle
    dll.SetInformationJobObject.argtypes = [handle, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    dll.SetInformationJobObject.restype = wintypes.BOOL
    dll.QueryInformationJobObject.argtypes = [
        handle, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    dll.QueryInformationJobObject.restype = wintypes.BOOL
    dll.CreateProcessW.argtypes = [
        wintypes.LPCWSTR, wintypes.LPWSTR, ctypes.c_void_p, ctypes.c_void_p,
        wintypes.BOOL, wintypes.DWORD, ctypes.c_void_p, wintypes.LPCWSTR,
        ctypes.POINTER(_StartupInfo), ctypes.POINTER(_ProcessInfo),
    ]
    dll.CreateProcessW.restype = wintypes.BOOL
    dll.AssignProcessToJobObject.argtypes = [handle, handle]
    dll.AssignProcessToJobObject.restype = wintypes.BOOL
    dll.ResumeThread.argtypes = [handle]
    dll.ResumeThread.restype = wintypes.DWORD
    dll.CloseHandle.argtypes = [handle]
    dll.CloseHandle.restype = wintypes.BOOL
    dll.TerminateProcess.argtypes = [handle, wintypes.UINT]
    dll.TerminateProcess.restype = wintypes.BOOL
    dll.TerminateJobObject.argtypes = [handle, wintypes.UINT]
    dll.TerminateJobObject.restype = wintypes.BOOL
    dll.WaitForSingleObject.argtypes = [handle, wintypes.DWORD]
    dll.WaitForSingleObject.restype = wintypes.DWORD
    dll.GetExitCodeProcess.argtypes = [handle, ctypes.POINTER(wintypes.DWORD)]
    dll.GetExitCodeProcess.restype = wintypes.BOOL
    dll.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    dll.OpenProcess.restype = handle
    return dll


class WindowsJobChild:
    """Popen-compatible subset; CloseHandle(job) kills every attached child."""

    def __init__(self, api, job: int, process: int, pid: int):
        self._api = api
        self._job = job
        self._handle = process  # Exposed only to existing PSAPI RSS sampler
        self.pid = pid
        self.returncode: int | None = None
        self._closed = False

    def poll(self) -> int | None:
        if self.returncode is not None:
            return self.returncode
        if self._api.WaitForSingleObject(self._handle, 0) != WAIT_OBJECT_0:
            return None
        result = wintypes.DWORD()
        if not self._api.GetExitCodeProcess(self._handle, ctypes.byref(result)):
            raise OSError("WIN32_PROCESS_EXIT_STATUS_UNAVAILABLE")
        value = int(result.value)
        self.returncode = value if value < 0x80000000 else value - 0x100000000
        return self.returncode

    def wait(self, timeout: float | None = None) -> int:
        if timeout is None:
            milliseconds = 0xFFFFFFFF
        else:
            milliseconds = max(0, int(timeout * 1000))
        wait_result = self._api.WaitForSingleObject(self._handle, milliseconds)
        if wait_result == WAIT_TIMEOUT:
            raise subprocess.TimeoutExpired("guarded synthetic child", timeout)
        if wait_result != WAIT_OBJECT_0:
            raise OSError("WIN32_JOB_CHILD_WAIT_FAILED")
        code = self.poll()
        if code is None:
            raise OSError("WIN32_JOB_CHILD_STATUS_MISSING")
        return code

    def kill(self) -> None:
        if not self._closed and not self._api.TerminateJobObject(self._job, 1):
            raise OSError("WIN32_JOB_TERMINATION_FAILED")

    def _read_job_limits(self) -> _ExtendedLimits | None:
        if self._closed:
            return None
        info = _ExtendedLimits()
        if not self._api.QueryInformationJobObject(
            self._job, JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS,
            ctypes.byref(info), ctypes.sizeof(info), None,
        ):
            return None
        return info

    def _job_process_ids(self) -> tuple[int, ...] | None:
        """Read the kernel's *active* job process IDs; refuse partial lists."""
        if self._closed:
            return None
        info = _JobProcessIds()
        if not self._api.QueryInformationJobObject(
            self._job, JOB_OBJECT_BASIC_PROCESS_ID_LIST_CLASS,
            ctypes.byref(info), ctypes.sizeof(info), None,
        ):
            return None
        count = int(info.NumberOfProcessIdsInList)
        assigned = int(info.NumberOfAssignedProcesses)
        if count > MAX_JOB_PIDS or assigned != count:
            # Truncated or racing snapshots must not be accepted as a
            # complete process-tree working-set measurement.
            return None
        pids = tuple(int(info.ProcessIdList[i]) for i in range(count))
        if any(pid <= 0 for pid in pids) or len(set(pids)) != count:
            return None
        return pids

    def current_tree_process_count(self) -> int | None:
        ids = self._job_process_ids()
        return len(ids) if ids is not None else None

    def current_tree_working_set_bytes(self) -> int | None:
        """Sum resident working sets across every *active* job PID.

        This is sampled total RSS, NOT the kernel peak committed-memory
        counter. Shared code/data pages can be counted for multiple PIDs.
        An inaccessible child or incomplete process-list snapshot returns
        None rather than silently producing a partial (false-low) total.
        """
        ids = self._job_process_ids()
        if ids is None:
            return None
        if not ids:
            return 0
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        psapi.GetProcessMemoryInfo.argtypes = [
            wintypes.HANDLE, ctypes.POINTER(_ProcessMemoryCounters),
            wintypes.DWORD,
        ]
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
        total = 0
        for pid in ids:
            process = self._api.OpenProcess(
                PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid,
            )
            if not process:
                return None
            try:
                counters = _ProcessMemoryCounters()
                counters.cb = ctypes.sizeof(counters)
                if not psapi.GetProcessMemoryInfo(
                    process, ctypes.byref(counters), ctypes.sizeof(counters),
                ):
                    return None
                total += int(counters.WorkingSetSize)
            finally:
                self._api.CloseHandle(process)
        return total

    def configured_job_limit_bytes(self) -> int | None:
        info = self._read_job_limits()
        return int(info.JobMemoryLimit) if info is not None else None

    def peak_job_commit_bytes(self) -> int | None:
        info = self._read_job_limits()
        return int(info.PeakJobMemoryUsed) if info is not None else None

    def close(self) -> None:
        if not self._closed:
            # KILL_ON_JOB_CLOSE also catches descendants that outlived the
            # direct child; process handle is closed only after job cleanup.
            self._api.CloseHandle(self._job)
            self._api.CloseHandle(self._handle)
            self._closed = True


def start_windows_job_child(
    argv: list[str], *, job_limit_bytes: int, active_process_limit: int = 3,
) -> WindowsJobChild:
    """CreateProcessW suspended -> AssignProcessToJobObject -> ResumeThread.

    No uncontained command runs if assignment fails. Callers must supply the
    internal fixed synthetic workload, never user-provided CLI commands.
    """
    if sys.platform != "win32":
        raise OSError("WINDOWS_JOB_OBJECT_UNAVAILABLE")
    if type(job_limit_bytes) is not int or not 8 * 1024**2 <= job_limit_bytes <= 256 * 1024**2:
        raise ValueError("Job memory bound must be 8–256 MiB")
    if type(active_process_limit) is not int or not 1 <= active_process_limit <= 4:
        raise ValueError("Job process count must be 1–4")
    if not argv or not all(isinstance(item, str) and item for item in argv):
        raise ValueError("No child command")
    api = _api()
    job = api.CreateJobObjectW(None, None)
    if not job:
        raise OSError("WIN32_JOB_CREATE_FAILED")
    info = _ExtendedLimits()
    info.BasicLimitInformation.LimitFlags = (
        JOB_OBJECT_LIMIT_JOB_MEMORY | JOB_OBJECT_LIMIT_ACTIVE_PROCESS
        | JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    )
    info.BasicLimitInformation.ActiveProcessLimit = active_process_limit
    info.JobMemoryLimit = job_limit_bytes
    pi = _ProcessInfo()
    try:
        if not api.SetInformationJobObject(
            job, JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS,
            ctypes.byref(info), ctypes.sizeof(info),
        ):
            raise OSError("WIN32_JOB_LIMIT_CONFIGURATION_FAILED")
        readback = _ExtendedLimits()
        if not api.QueryInformationJobObject(
            job, JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS,
            ctypes.byref(readback), ctypes.sizeof(readback), None,
        ):
            raise OSError("WIN32_JOB_LIMIT_READBACK_FAILED")
        required = (
            JOB_OBJECT_LIMIT_JOB_MEMORY | JOB_OBJECT_LIMIT_ACTIVE_PROCESS
            | JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        )
        if (
            readback.BasicLimitInformation.LimitFlags & required != required
            or readback.JobMemoryLimit != job_limit_bytes
            or readback.BasicLimitInformation.ActiveProcessLimit != active_process_limit
        ):
            raise OSError("WIN32_JOB_LIMIT_READBACK_MISMATCH")
        # The kernel itself must acknowledge the exact aggregate budget
        # before even creating the suspended child.
        startup = _StartupInfo()
        startup.cb = ctypes.sizeof(startup)
        command = ctypes.create_unicode_buffer(subprocess.list2cmdline(argv))
        flags = CREATE_SUSPENDED | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
        if not api.CreateProcessW(
            None, command, None, None, False, flags, None, None,
            ctypes.byref(startup), ctypes.byref(pi),
        ):
            raise OSError("WIN32_SUSPENDED_CHILD_CREATE_FAILED")
        try:
            if not api.AssignProcessToJobObject(job, pi.hProcess):
                raise OSError("WIN32_JOB_ASSIGNMENT_FAILED")
            if api.ResumeThread(pi.hThread) == INVALID_RESUME_THREAD_RESULT:
                raise OSError("WIN32_CHILD_RESUME_FAILED")
            return WindowsJobChild(api, int(job), int(pi.hProcess), int(pi.dwProcessId))
        except BaseException:
            api.TerminateProcess(pi.hProcess, 1)
            api.WaitForSingleObject(pi.hProcess, 3000)
            api.CloseHandle(pi.hProcess)
            raise
        finally:
            api.CloseHandle(pi.hThread)
    except BaseException:
        api.CloseHandle(job)
        raise
