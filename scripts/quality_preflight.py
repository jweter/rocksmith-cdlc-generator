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
)

# Base branches to look for a merge-base against, in preference order.
_DIFF_BASE_CANDIDATES: tuple[str, ...] = ("origin/main", "main")


def resolve_diff_base() -> str:
    """Resolve a revision to diff the working tree against for whitespace checks.

    The no-argument form of ``git diff --check`` only compares the working
    tree with the index, so it silently ignores every staged file and every
    already-committed branch change -- exactly the changes that make up a
    proposed patch by the time someone is about to open or update a pull
    request. Diffing against the merge-base with the target branch instead
    covers the whole patch (committed, staged, and unstaged) regardless of
    whether earlier commits on this branch have already been made.
    """
    for ref in _DIFF_BASE_CANDIDATES:
        verify = subprocess.run(  # noqa: S603
            ("git", "rev-parse", "--verify", "--quiet", ref),
            capture_output=True,
            text=True,
            check=False,
        )
        if verify.returncode != 0:
            continue
        merge_base = subprocess.run(  # noqa: S603
            ("git", "merge-base", ref, "HEAD"),
            capture_output=True,
            text=True,
            check=False,
        )
        base = merge_base.stdout.strip()
        if merge_base.returncode == 0 and base:
            return base
    # No known base branch is reachable (e.g. a shallow clone without
    # "main"/"origin/main"). Fall back to HEAD so the check still runs
    # instead of crashing, even though it will then only catch unstaged
    # working-tree changes.
    return "HEAD"


def diff_check_command(base: str | None = None) -> Command:
    """Whitespace-check the working tree against ``base`` (or the resolved
    merge-base when ``base`` is omitted).

    This form reads working-tree file contents, so it also covers committed
    and unstaged changes. It does **not** cover a file that is staged with a
    whitespace error and then edited again in the working tree without being
    re-staged (git status ``MM``): the working tree looks clean even though
    the index -- what a plain ``git commit`` would actually record -- still
    has the error. ``cached_diff_check_command()`` covers that case.
    """
    return ("git", "diff", "--check", base or resolve_diff_base())


def cached_diff_check_command(base: str | None = None) -> Command:
    """Whitespace-check the *index* (staged content) against ``base``.

    Complements :func:`diff_check_command`: a whitespace error that is
    staged and then only fixed in the working tree copy (git status
    ``MM``) is invisible to the working-tree form above, but a plain
    ``git commit`` right now would still record the broken staged content.
    Diffing ``--cached`` catches that staged-only regression.
    """
    return ("git", "diff", "--cached", "--check", base or resolve_diff_base())


def diff_check_commands() -> tuple[Command, Command]:
    """Both whitespace-check forms needed to cover the whole proposed patch:
    working tree (committed + unstaged) and index (staged) content.
    """
    base = resolve_diff_base()
    return (diff_check_command(base), cached_diff_check_command(base))


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

    returncode = run((*CHECKS, *diff_check_commands()))
    if returncode != 0:
        return returncode
    if args.windows_bridge:
        if sys.platform != "win32":
            parser.error("--windows-bridge requires Windows")
        return run(WINDOWS_EXTRA)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
