from __future__ import annotations

import argparse
from pathlib import Path

from .score_arrangement_fanout import import_confirmed_score_arrangements


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cdlc-score-import",
        description=(
            "Import arrangement-specific normalized sources from human-confirmed "
            "Bass/Lead/Rhythm mappings in a registered project score."
        ),
    )
    parser.add_argument("project", type=Path, help="CDLC project directory")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = import_confirmed_score_arrangements(args.project)
    print(f"Score: {result.source_sha256}")
    for role, output in sorted(result.arrangements.items(), key=lambda item: item[0].value):
        print(f"{role.value}: {output}")
    print(f"Manifest: {result.manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
