from __future__ import annotations

import argparse
from pathlib import Path

from .eof_bridge import build_eof_launch_command, launch_project_score_in_eof


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cdlc-eof",
        description="Open the project's immutable registered GP3/GP4/GP5 score in Editor on Fire for independent review",
    )
    parser.add_argument("project", type=Path)
    parser.add_argument(
        "--executable",
        type=Path,
        help="Optional path to eof.exe. Otherwise ROCKSMITH_CDLC_EOF_EXE, EOF_EXE, or PATH is used.",
    )
    parser.add_argument(
        "--show-command",
        action="store_true",
        help="Print the verified launch command without starting EOF.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.show_command:
        print(build_eof_launch_command(args.project, eof_executable=args.executable))
        return
    launch_project_score_in_eof(args.project, eof_executable=args.executable)


if __name__ == "__main__":
    main()
