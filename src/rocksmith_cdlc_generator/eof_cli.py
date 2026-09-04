from __future__ import annotations

import argparse
from pathlib import Path

from .eof_bridge import build_eof_launch_command, launch_project_score_in_eof
from .eof_hand_position_project import write_project_eof_hand_position_status
from .eof_project_report import write_project_eof_compatibility_report
from .eof_recording_clock import write_project_eof_recording_clock_report
from .eof_rest_boundary_project import write_project_eof_rest_boundary_report
from .eof_score_triangulation import write_project_eof_score_triangulation_report
from .eof_short_note_truncation_project import write_project_eof_short_note_truncation_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cdlc-eof",
        description=(
            "Open the project's immutable registered GP3/GP4/GP5 score in Editor on Fire "
            "or validate source-bound EOF / alternate-score review evidence"
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
        "--compare-recording-clock-fixture",
        type=Path,
        help=(
            "Compare sparse EOF-observed recording timestamps with the current promoted shared "
            "timeline and write review/eof_recording_clock_report.json."
        ),
    )
    parser.add_argument(
        "--compare-score",
        type=Path,
        help=(
            "Compare a private alternate GP3/GP4/GP5 full score with the project's registered "
            "score across Bass, Lead, and Rhythm and write review/eof_score_triangulation_report.json."
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
        "--check-short-note-truncation",
        action="store_true",
        help=(
            "Compare the current registered GP score against EOF's default short-note/"
            "staccato/mute sustain-truncation preferences and write "
            "review/eof_short_note_truncation_report.json without launching EOF."
        ),
    )
    parser.add_argument(
        "--check-rest-boundary",
        action="store_true",
        help=(
            "Compare the current registered GP score's imported note sustains against EOF's "
            "explicit-rest boundary invariant and write review/eof_rest_boundary_report.json "
            "without launching EOF."
        ),
    )
    parser.add_argument(
        "--instrument",
        choices=("bass", "lead", "rhythm"),
        default="bass",
        help="Arrangement role used by source-relative EOF evidence operations (default: bass).",
    )
    parser.add_argument(
        "--timing-tolerance-seconds",
        type=float,
        default=1e-6,
        help=(
            "Non-negative timing tolerance. Source-relative --compare-fixture defaults to 0.000001; "
            "recording-clock comparison treats values below 0.05 as 0.05 seconds unless explicitly larger."
        ),
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    operations = [
        args.compare_fixture is not None,
        args.compare_recording_clock_fixture is not None,
        args.compare_score is not None,
        args.validate_hand_positions is not None,
        args.check_short_note_truncation,
        args.check_rest_boundary,
    ]
    if sum(operations) > 1:
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
    if args.compare_recording_clock_fixture is not None:
        tolerance = max(0.05, args.timing_tolerance_seconds)
        destination, report = write_project_eof_recording_clock_report(
            args.project,
            args.compare_recording_clock_fixture,
            timing_tolerance_seconds=tolerance,
        )
        print(report.model_dump_json(indent=2))
        print(f"Wrote advisory EOF recording-clock report: {destination}")
        return
    if args.compare_score is not None:
        destination, report = write_project_eof_score_triangulation_report(
            args.project,
            args.compare_score,
        )
        print(report.model_dump_json(indent=2))
        print(f"Wrote advisory alternate-score triangulation report: {destination}")
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
    if args.check_short_note_truncation:
        destination, report = write_project_eof_short_note_truncation_report(
            args.project,
            instrument=args.instrument,
        )
        print(report.model_dump_json(indent=2))
        print(f"Wrote advisory EOF short-note-truncation report: {destination}")
        return
    if args.check_rest_boundary:
        destination, report = write_project_eof_rest_boundary_report(
            args.project,
            instrument=args.instrument,
            overlap_tolerance_seconds=args.timing_tolerance_seconds,
        )
        print(report.model_dump_json(indent=2))
        print(f"Wrote advisory EOF rest-boundary report: {destination}")
        return
    if args.show_command:
        print(build_eof_launch_command(args.project, eof_executable=args.executable))
        return
    launch_project_score_in_eof(args.project, eof_executable=args.executable)


if __name__ == "__main__":
    main()
