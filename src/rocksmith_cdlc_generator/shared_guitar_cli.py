from __future__ import annotations

import argparse
from pathlib import Path

from .shared_guitar_bounds import build_project_shared_guitar_chart_bounded


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cdlc-build-shared-guitar",
        description="Build Lead or Rhythm from the current reviewed shared timeline and score fan-out.",
    )
    parser.add_argument("project", type=Path)
    parser.add_argument("--instrument", choices=["lead", "rhythm"], required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    output = build_project_shared_guitar_chart_bounded(
        args.project,
        arrangement=args.instrument,
    )
    print(output)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
