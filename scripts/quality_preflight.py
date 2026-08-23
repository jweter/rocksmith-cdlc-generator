"""Run the Rocksmith generator's repository-specific local preflight."""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Sequence

Command = tuple[str, ...]

CHECKS: tuple[Command, ...] = (
    (sys.executable, "scripts/check_automation_readiness.py"),
    (sys.executable, "-m", "compileall", "-q", "src", "tests"),
    (sys.executable, "-m", "pytest", "-q"),
    ("cdlc", "--help"),
    (sys.executable, "-m", "pip", "check"),
    ("git", "diff", "--check"),
)

WINDOWS_EXTRA: tuple[Command, ...] = (
    (
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        "scripts/bootstrap_psarc_bridge.ps1",
    ),
)


def run(commands: Sequence[Command]) -> int:
    """Run commands in order and stop on the first failure."""
    for command in commands:
        print(f"+ {' '.join(command)}", flush=True)
        returncode = subprocess.run(command, check=False).returncode  # noqa: S603
        if returncode != 0:
            return returncode
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run Linux/portable CI parity and optionally the Windows PSARC bridge build."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--windows-bridge",
        action="store_true",
        help="Also build the pinned Rocksmith2014.NET PSARC bridge on Windows.",
    )
    args = parser.parse_args(argv)

    returncode = run(CHECKS)
    if returncode != 0:
        return returncode
    if args.windows_bridge:
        if sys.platform != "win32":
            parser.error("--windows-bridge requires Windows")
        return run(WINDOWS_EXTRA)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
