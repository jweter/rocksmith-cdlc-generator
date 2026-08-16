from __future__ import annotations

import sys

from rocksmith_cdlc_generator.desktop_runner import run_desktop_worker
from rocksmith_cdlc_generator.diagnostic_guided_desktop import main


_DESKTOP_WORKER_FLAG = "--desktop-worker"


def run() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == _DESKTOP_WORKER_FLAG:
        return run_desktop_worker(sys.argv[2:])
    main()
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
