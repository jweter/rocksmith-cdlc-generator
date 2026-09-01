from __future__ import annotations

import argparse
from pathlib import Path

from .printed_score_project import create_printed_score_project
from .private_score_bundle import PrivateScoreBundleSpec


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="cdlc-score-project",
        description=(
            "Create a desktop-openable score-only project and privately register all "
            "hash-bound printed-score page images"
        ),
    )
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--projects-root", required=True, type=Path)
    parser.add_argument("--movement")
    parser.add_argument(
        "--list-movements",
        action="store_true",
        help="Print movement IDs/titles from the manifest and exit without creating a project",
    )
    args = parser.parse_args(argv)

    if args.list_movements:
        spec = PrivateScoreBundleSpec.read_yaml(args.manifest)
        for movement in spec.movements:
            print(f"{movement.movement_id}\t{movement.title}\tpages {movement.start_page}-{movement.end_page}")
        return 0

    project = create_printed_score_project(
        spec_path=args.manifest,
        source_dir=args.source_dir,
        projects_root=args.projects_root,
        movement_id=args.movement,
    )
    print(project)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
