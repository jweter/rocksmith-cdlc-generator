from __future__ import annotations

import sys

from rocksmith_cdlc_generator.desktop_entrypoint import main
from rocksmith_cdlc_generator.desktop_runner import run_desktop_worker
from rocksmith_cdlc_generator.unattended_worker_cli import main as run_unattended_worker_cli


_DESKTOP_WORKER_FLAG = "--desktop-worker"
_UNATTENDED_WORKER_FLAG = "--unattended-worker"


def run() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == _DESKTOP_WORKER_FLAG:
        return run_desktop_worker(sys.argv[2:])
    if len(sys.argv) > 1 and sys.argv[1] == _UNATTENDED_WORKER_FLAG:
        return run_unattended_worker_cli(sys.argv[2:])
    main()
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
