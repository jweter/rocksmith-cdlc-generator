from __future__ import annotations

import argparse
from pathlib import Path

from .multi_arrangement_plan import build_multi_arrangement_workflow_plan


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cdlc-plan",
        description="Show the ordered automatic and human-gated path to Bass, Lead, and Rhythm drafts.",
    )
    parser.add_argument("project", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    plan = build_multi_arrangement_workflow_plan(args.project)
    print(plan.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
