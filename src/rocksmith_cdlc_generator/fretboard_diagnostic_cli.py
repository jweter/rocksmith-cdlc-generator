from __future__ import annotations

import argparse
from pathlib import Path

from .project_fretboard_diagnostics import build_project_fretboard_diagnostic


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cdlc-fretboard",
        description=(
            "Inspect pitch-correct fretboard candidates and imported source-position diagnostics "
            "for one current human-confirmed project arrangement."
        ),
    )
    parser.add_argument("project", type=Path)
    parser.add_argument(
        "--instrument",
        choices=("bass", "lead", "rhythm"),
        default="bass",
        help="Human-confirmed arrangement role to inspect (default: bass).",
    )
    parser.add_argument(
        "--max-fret",
        type=int,
        default=24,
        help="Maximum fret included in the pitch-correct candidate search space (default: 24).",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    diagnostic = build_project_fretboard_diagnostic(
        args.project,
        arrangement=args.instrument,
        max_fret=args.max_fret,
    )
    print(diagnostic.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
