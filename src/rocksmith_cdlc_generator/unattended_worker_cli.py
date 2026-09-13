from __future__ import annotations

import argparse
from pathlib import Path
import sys
import time

from .unattended_worker import (
    format_worker_report,
    load_worker_config,
    run_unattended_worker,
)

_STALE_LOCK_SECONDS = 6 * 60 * 60


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cdlc-local-worker",
        description=(
            "Run private Product Reality and timing-health checks unattended on the local machine. "
            "Private media never leaves the computer."
        ),
    )
    parser.add_argument("--config", type=Path, help="Optional local worker JSON config")
    parser.add_argument(
        "--repo-root",
        type=Path,
        help="Optional source checkout root used only to discover gitignored private scenarios.",
    )
    parser.add_argument(
        "--strict-exit",
        action="store_true",
        help="Exit non-zero for Product Reality FAIL/REVIEW_REQUIRED. Scheduled runs default to exit 0.",
    )
    return parser


def _clear_stale_lock(config_path: Path | None, repo_root: Path | None) -> None:
    """Recover from a crashed prior worker without defeating normal overlap protection."""

    config = load_worker_config(config_path, repo_root=repo_root)
    if config.state_dir is None:
        return
    lock = config.state_dir / "worker.lock"
    try:
        age = time.time() - lock.stat().st_mtime
    except OSError:
        return
    if age > _STALE_LOCK_SECONDS:
        lock.unlink(missing_ok=True)


def _emit(message: str) -> None:
    """Write only when a console exists; PyInstaller --windowed sets stdout to None."""

    if sys.stdout is not None:
        print(message)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _clear_stale_lock(args.config, args.repo_root)
    result = run_unattended_worker(config_path=args.config, repo_root=args.repo_root)
    _emit(format_worker_report(result.report))
    _emit(f"Worker report: {result.report_path}")
    if args.strict_exit:
        if result.report.status == "FAIL":
            return 2
        if result.report.status == "REVIEW_REQUIRED":
            return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
