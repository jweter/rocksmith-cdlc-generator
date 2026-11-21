"""No-install/no-execution upstream auto-cdlc environment doctor."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .auto_cdlc_readiness import inspect_upstream_readiness


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cdlc-auto-cdlc-doctor",
        description=(
            "Read-only audit: report which local prerequisites block the "
            "pinned auto-cdlc synthetic transcription or optional Wwise. "
            "No model is imported, downloaded or executed and no files are written."
        ),
    )
    parser.add_argument("--fixture-dir", type=Path)
    parser.add_argument("--upstream-checkout", type=Path)
    parser.add_argument("--python-313", type=Path)
    parser.add_argument("--run-parent", type=Path, help="Existing local directory with space for a future sandbox")
    parser.add_argument("--wwise-console", type=Path, help="Optional explicitly supplied WwiseConsole.exe or Wwise root")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        report = inspect_upstream_readiness(
            fixture_dir=args.fixture_dir,
            upstream_checkout=args.upstream_checkout,
            python_313_exe=args.python_313,
            run_parent=args.run_parent,
            wwise_console=args.wwise_console,
        )
    except (OSError, ValueError) as exc:
        print(f"auto-cdlc doctor error: {type(exc).__name__}", file=sys.stderr)
        raise SystemExit(1) from exc
    print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))
    raise SystemExit(0 if report["synthetic_transcription_ready"] else 2)


if __name__ == "__main__":
    main()
