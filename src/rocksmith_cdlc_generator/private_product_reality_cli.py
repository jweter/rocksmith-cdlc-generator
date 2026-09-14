from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING

from .beats import read_tempo_map
from .eof_recording_clock import load_current_project_eof_recording_clock_report
from .hashing import sha256_file
from .mobile_eof_differential import build_mobile_eof_differential
from .mobile_product_reality import build_mobile_review_report, render_mobile_review
from .private_product_reality import (
    format_private_product_reality_report,
    load_private_product_reality_scenario,
    run_private_product_reality,
)
from .timing_review import authoritative_tempo_map_path

if TYPE_CHECKING:
    from .beats import TempoMap
    from .private_product_reality import PrivateProductRealityEvidence


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
    parser.add_argument(
        "--mobile-review",
        type=Path,
        help=(
            "Optional path to also write a privacy-safe, self-contained iPhone-readable "
            "review artifact (issue #569) alongside the JSON evidence."
        ),
    )
    return parser


def _load_mobile_review_tempo_map(
    scenario_path: Path,
    evidence: "PrivateProductRealityEvidence",
) -> tuple["TempoMap | None", str | None]:
    """Re-read the live authoritative tempo map for a mobile review artifact.

    The evidence digest remains authoritative. If the map cannot be read, phase display stays
    UNKNOWN. If the map changed after evidence collection, its current digest is still passed to
    ``build_mobile_review_report`` so that function's digest check fails closed instead of
    presenting phase values from stale/mismatched authority.
    """
    if evidence.tempo_map_sha256 is None:
        return None, None

    try:
        scenario = load_private_product_reality_scenario(scenario_path)
        tempo_path = authoritative_tempo_map_path(scenario.project_dir)
        return read_tempo_map(tempo_path), sha256_file(tempo_path)
    except (OSError, ValueError):
        return None, None


def _load_mobile_review_eof_differential(scenario_path: Path) -> dict[str, object] | None:
    """Load only current, source-bound EOF parity evidence for mobile review.

    The authoritative loader rejects stale score/recording/source-track/shared-timeline evidence.
    Missing or stale EOF evidence is therefore treated as unavailable rather than fabricated.
    The projection itself strips private/source payload fields before anything reaches HTML.
    """
    try:
        scenario = load_private_product_reality_scenario(scenario_path)
        eof_report = load_current_project_eof_recording_clock_report(scenario.project_dir)
        if eof_report is None:
            return None
        return build_mobile_eof_differential(eof_report)
    except (OSError, ValueError):
        return None


def main() -> None:
    args = build_parser().parse_args()
    evidence, destination = run_private_product_reality(
        args.scenario,
        results_dir=args.results_dir,
    )
    print(format_private_product_reality_report(evidence))
    print(f"Evidence: {destination}")
    if args.mobile_review is not None:
        tempo_map, tempo_map_sha256 = _load_mobile_review_tempo_map(args.scenario, evidence)
        eof_differential = _load_mobile_review_eof_differential(args.scenario)
        report = build_mobile_review_report(
            evidence,
            tempo_map=tempo_map,
            tempo_map_sha256=tempo_map_sha256,
            eof_differential=eof_differential,
        )
        html = render_mobile_review(report)
        mobile_path = args.mobile_review.expanduser().resolve()
        mobile_path.parent.mkdir(parents=True, exist_ok=True)
        mobile_path.write_text(html, encoding="utf-8")
        print(f"Mobile review: {mobile_path}")
    if evidence.result == "FAIL":
        raise SystemExit(2)
    if evidence.result == "REVIEW_REQUIRED":
        raise SystemExit(3)


if __name__ == "__main__":
    main()
