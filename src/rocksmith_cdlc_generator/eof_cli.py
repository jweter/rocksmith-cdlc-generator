from __future__ import annotations

import argparse
from pathlib import Path

from .eof_bridge import build_eof_launch_command, launch_project_score_in_eof
from .eof_hand_position_project import write_project_eof_hand_position_status
from .eof_project_report import write_project_eof_compatibility_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cdlc-eof",
        description=(
            "Open the project's immutable registered GP3/GP4/GP5 score in Editor on Fire "
            "or validate source-bound EOF review evidence"
        ),
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
    parser.add_argument(
        "--compare-fixture",
        type=Path,
        help=(
            "Compare the current registered GP score with a source-bound EOF compatibility "
            "fixture and write review/eof_compatibility_report.json without launching EOF."
        ),
    )
    parser.add_argument(
        "--validate-hand-positions",
        type=Path,
        help=(
            "Validate a source-bound EOF fret-hand-position fixture against the current "
            "registered GP score and write review/eof_hand_position_status.json."
        ),
    )
    parser.add_argument(
        "--instrument",
        choices=("bass", "lead", "rhythm"),
        default="bass",
        help="Arrangement role used when reparsing the fixture's exact source track (default: bass).",
    )
    parser.add_argument(
        "--timing-tolerance-seconds",
        type=float,
        default=1e-6,
        help="Non-negative timing comparison tolerance for --compare-fixture (default: 0.000001).",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.compare_fixture is not None and args.validate_hand_positions is not None:
        raise SystemExit("Choose only one EOF evidence operation per invocation.")
    if args.compare_fixture is not None:
        destination, report = write_project_eof_compatibility_report(
            args.project,
            args.compare_fixture,
            instrument=args.instrument,
            timing_tolerance_seconds=args.timing_tolerance_seconds,
        )
        print(report.model_dump_json(indent=2))
        print(f"Wrote advisory EOF compatibility report: {destination}")
        return
    if args.validate_hand_positions is not None:
        destination, status = write_project_eof_hand_position_status(
            args.project,
            args.validate_hand_positions,
            instrument=args.instrument,
        )
        print(status.model_dump_json(indent=2))
        print(f"Wrote advisory EOF hand-position status: {destination}")
        return
    if args.show_command:
        print(build_eof_launch_command(args.project, eof_executable=args.executable))
        return
    launch_project_score_in_eof(args.project, eof_executable=args.executable)


if __name__ == "__main__":
    main()
