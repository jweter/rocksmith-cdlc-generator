from __future__ import annotations

import threading

from .diagnostic_guided_desktop import main as run_desktop
from .windows_unattended_worker import ensure_windows_worker_registered


def _register_in_background() -> None:
    threading.Thread(
        target=ensure_windows_worker_registered,
        name="rocksmith-unattended-worker-registration",
        daemon=True,
    ).start()


def main() -> None:
    """Launch the desktop while silently ensuring the private idle worker exists."""

    _register_in_background()
    run_desktop()
