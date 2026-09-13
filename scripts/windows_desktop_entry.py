from __future__ import annotations

import sys
import threading

from rocksmith_cdlc_generator.desktop_runner import run_desktop_worker
from rocksmith_cdlc_generator.diagnostic_guided_desktop import main
from rocksmith_cdlc_generator.unattended_worker_cli import main as run_unattended_worker_cli
from rocksmith_cdlc_generator.windows_unattended_worker import ensure_windows_worker_registered


_DESKTOP_WORKER_FLAG = "--desktop-worker"
_UNATTENDED_WORKER_FLAG = "--unattended-worker"


def _register_unattended_worker_in_background() -> None:
    """Register the idle task without adding startup latency or UI prompts."""

    threading.Thread(
        target=ensure_windows_worker_registered,
        name="rocksmith-unattended-worker-registration",
        daemon=True,
    ).start()


def run() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == _DESKTOP_WORKER_FLAG:
        return run_desktop_worker(sys.argv[2:])
    if len(sys.argv) > 1 and sys.argv[1] == _UNATTENDED_WORKER_FLAG:
        return run_unattended_worker_cli(sys.argv[2:])
    _register_unattended_worker_in_background()
    main()
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
