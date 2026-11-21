"""Opt-in pinned external auto-cdlc synthetic run, without installing models."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .auto_cdlc_executor import UpstreamRunError, run_pinned_upstream_synthetic
from .auto_cdlc_truth import KnownTruthError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cdlc-auto-cdlc-run",
        description=(
            "Safely admit an explicitly approved, pinned upstream auto-cdlc "
            "checkout with a preinstalled Python 3.13 model runtime to process "
            "only our reproducible copyright-free synthetic test recording. "
            "No game writes, installer, model fetch or private music input."
        ),
    )
    parser.add_argument("--fixture-dir", type=Path, required=True)
    parser.add_argument("--upstream-checkout", type=Path, required=True)
    parser.add_argument("--python-313", dest="python_313_exe", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True, help="New, empty local run directory outside code/fixture folders")
    parser.add_argument("--confirm-noncommercial", action="store_true", required=True)
    parser.add_argument("--timeout", type=int, default=3600)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        result = run_pinned_upstream_synthetic(
            args.fixture_dir,
            upstream_checkout=args.upstream_checkout,
            python_313_exe=args.python_313_exe,
            run_dir=args.run_dir,
            confirm_noncommercial=args.confirm_noncommercial,
            timeout_seconds=args.timeout,
        )
    except (KnownTruthError, UpstreamRunError, ValueError, OSError) as exc:
        print(f"upstream synthetic runner refused or failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    print(f"Synthetic upstream execution: {result['status']}")
    print("Only original synthetic known-truth accuracy was tested, never real songs or Rocksmith gameplay.")
    raise SystemExit(0 if result["status"] == "PASS" else 2)


if __name__ == "__main__":
    main()
