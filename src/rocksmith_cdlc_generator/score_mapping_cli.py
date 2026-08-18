from __future__ import annotations

import argparse
from pathlib import Path

from .score_mapping_coverage import summarize_score_mapping_coverage
from .score_mapping_review import confirm_score_mapping, load_score_for_mapping_review
from .score_source import ArrangementRole


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cdlc-score-map",
        description="Inspect or explicitly human-confirm Bass/Lead/Rhythm tracks in a registered complete score",
    )
    parser.add_argument("project", type=Path)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("show", help="Show the verified score inventory and mapping review state")
    subparsers.add_parser(
        "coverage",
        help="Show mapped roles plus playable score tracks not referenced by any role mapping",
    )

    confirm = subparsers.add_parser("confirm", help="Confirm one arrangement role to one known score track")
    confirm.add_argument("role", choices=[role.value for role in ArrangementRole])
    confirm.add_argument("track_index", type=int)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "show":
        score = load_score_for_mapping_review(args.project)
        print(score.model_dump_json(indent=2))
        return

    if args.command == "coverage":
        score = load_score_for_mapping_review(args.project)
        coverage = summarize_score_mapping_coverage(score)
        print(coverage.model_dump_json(indent=2))
        return

    mapping = confirm_score_mapping(
        args.project,
        role=ArrangementRole(args.role),
        source_track_index=args.track_index,
    )
    print(mapping.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
