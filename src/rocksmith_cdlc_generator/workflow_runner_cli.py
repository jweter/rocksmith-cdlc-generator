from __future__ import annotations

import argparse
from pathlib import Path

from .workflow_runner import run_automatic_first_draft


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cdlc-auto",
        description="Run deterministic first-draft stages until a human review gate is reached",
    )
    parser.add_argument("project", type=Path)
    parser.add_argument(
        "--max-steps",
        type=int,
        default=8,
        help="Safety bound on automatic stages executed in one invocation (default: 8)",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = run_automatic_first_draft(args.project, max_steps=args.max_steps)
    print(result.model_dump_json(indent=2))
    if result.stop_reason in {"step_failed", "no_progress"}:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
