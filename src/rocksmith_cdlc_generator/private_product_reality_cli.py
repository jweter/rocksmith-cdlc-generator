from __future__ import annotations

import argparse
from pathlib import Path

from .private_product_reality import (
    format_private_product_reality_report,
    run_private_product_reality,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cdlc-product-reality",
        description=(
            "Run deterministic private/local Product Reality acceptance without uploading "
            "private song or score material."
        ),
    )
    parser.add_argument(
        "--scenario",
        required=True,
        type=Path,
        help="Private local Product Reality scenario JSON",
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        help=(
            "Optional private evidence directory. Defaults to results/<scenario-id>/ "
            "beside the scenario file."
        ),
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    evidence, destination = run_private_product_reality(
        args.scenario,
        results_dir=args.results_dir,
    )
    print(format_private_product_reality_report(evidence))
    print(f"Evidence: {destination}")
    if evidence.result == "FAIL":
        raise SystemExit(2)
    if evidence.result == "REVIEW_REQUIRED":
        raise SystemExit(3)


if __name__ == "__main__":
    main()
