from __future__ import annotations

import argparse
from pathlib import Path

from .shared_timeline import load_current_shared_timeline, promote_shared_timeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cdlc-shared-timeline",
        description="Review and manage the one score-to-recording timeline shared by Bass, Lead, and Rhythm.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    promote = sub.add_parser(
        "promote",
        help="Accept the current authoritative shared-score Bass alignment as song-level timing authority",
    )
    promote.add_argument("project", type=Path)

    show = sub.add_parser("show", help="Show the current verified shared timeline")
    show.add_argument("project", type=Path)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "promote":
        print(promote_shared_timeline(args.project))
        return
    if args.command == "show":
        print(load_current_shared_timeline(args.project).model_dump_json(indent=2))
        return


if __name__ == "__main__":
    main()
