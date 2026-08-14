from __future__ import annotations

import argparse
from pathlib import Path

from .score_fanout import fanout_confirmed_score_mappings
from .score_source import ArrangementRole


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cdlc-score-fanout",
        description=(
            "Import human-confirmed Bass/Lead/Rhythm tracks from the registered complete score"
        ),
    )
    parser.add_argument("project", type=Path)
    parser.add_argument(
        "--role",
        action="append",
        choices=[role.value for role in ArrangementRole],
        help="Fan out only this human-confirmed role; repeat for multiple roles",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    roles = None if args.role is None else [ArrangementRole(value) for value in args.role]
    result = fanout_confirmed_score_mappings(args.project, roles=roles)
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
