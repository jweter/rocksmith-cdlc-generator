from __future__ import annotations

import argparse
from pathlib import Path

from .private_score_bundle import (
    PrivateScoreBundleSpec,
    register_private_score_bundle,
    summary_json,
    verify_private_score_bundle,
)
from .score_page_preprocessing import (
    normalize_movement_score_pages,
    normalize_registered_score_page,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cdlc-score-bundle",
        description="Register, verify, and preprocess private multi-page printed-score source sets",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    describe = sub.add_parser("describe", help="Validate and summarize a public-safe bundle YAML")
    describe.add_argument("--manifest", required=True, type=Path)

    register = sub.add_parser(
        "register",
        help="Copy/hash a complete private score image set into a local project",
    )
    register.add_argument("project", type=Path)
    register.add_argument("--manifest", required=True, type=Path)
    register.add_argument("--source-dir", required=True, type=Path)

    verify = sub.add_parser(
        "verify",
        help="Verify that every registered private score page still matches its recorded hash",
    )
    verify.add_argument("project", type=Path)

    normalize = sub.add_parser(
        "normalize",
        help="Create hash-bound normalized derivative page(s) for later notation/TAB recognition",
    )
    normalize.add_argument("project", type=Path)
    target = normalize.add_mutually_exclusive_group(required=True)
    target.add_argument("--page", type=int, help="Printed score page number to normalize")
    target.add_argument("--movement", help="Movement ID whose ordered score pages should be normalized")
    normalize.add_argument(
        "--max-long-edge",
        type=int,
        default=2200,
        help="Downscale derivatives so their long edge is at most this many pixels (default: 2200)",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "describe":
        spec = PrivateScoreBundleSpec.read_yaml(args.manifest)
        print(
            {
                "bundle_id": spec.bundle_id,
                "work_title": spec.work_title,
                "instrument": spec.instrument,
                "tuning": spec.tuning_name,
                "pages": len(spec.pages),
                "score_pages": len([page for page in spec.pages if page.kind == "score"]),
                "movements": [movement.movement_id for movement in spec.movements],
                "redistribution_allowed": spec.redistribution_allowed,
            }
        )
        return 0

    if args.command == "register":
        bundle = register_private_score_bundle(args.project, args.manifest, args.source_dir)
        print(summary_json(bundle))
        return 0

    if args.command == "verify":
        bundle = verify_private_score_bundle(args.project)
        print(summary_json(bundle))
        return 0

    if args.command == "normalize":
        if args.page is not None:
            result = normalize_registered_score_page(
                args.project,
                args.page,
                max_long_edge=args.max_long_edge,
            )
            print(result.model_dump_json(indent=2))
            return 0

        results = normalize_movement_score_pages(
            args.project,
            args.movement,
            max_long_edge=args.max_long_edge,
        )
        print("[\n" + ",\n".join(result.model_dump_json(indent=2) for result in results) + "\n]")
        return 0

    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
