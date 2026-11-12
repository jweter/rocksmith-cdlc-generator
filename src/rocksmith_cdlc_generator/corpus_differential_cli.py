"""Console entry point for the private corpus differential harness (issue #693 slice 6)."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .corpus_differential_harness import CorpusDifferentialHarnessError, LANES, run_corpus_differential_harness


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cdlc-corpus-diff",
        description=(
            "Offline harness for the private Rocksmith library regression corpus. Compares two "
            "local note JSON files with the generator-vs-reference comparator and writes only a "
            "sanitized aggregate report; it never reads or writes a PSARC, audio, or any other "
            "private song material."
        ),
    )
    parser.add_argument("--reference", required=True, type=Path, help="Reference arrangement note JSON file")
    parser.add_argument("--generated", required=True, type=Path, help="Generated/imported arrangement note JSON file")
    parser.add_argument("--trust-tier", required=True, choices=("A", "B", "C"), help="Trust tier of the reference")
    parser.add_argument(
        "--lane",
        required=True,
        choices=LANES,
        help=(
            "independent_generation: --generated is true generator output. importer_fidelity: "
            "--generated is notes the importer extracted from a score, which measures import "
            "correctness and must never be reported as independent generation accuracy."
        ),
    )
    parser.add_argument(
        "--out",
        required=True,
        type=Path,
        help="Output path for the sanitized report; refused if inside this repository checkout",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        differential, _report, resolved_out = run_corpus_differential_harness(
            reference_path=args.reference,
            generated_path=args.generated,
            trust_tier=args.trust_tier,
            lane=args.lane,
            out_path=args.out,
        )
    except CorpusDifferentialHarnessError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print(f"Verdict: {differential.verdict} (lane={args.lane}, trust_tier={args.trust_tier})")
    if args.lane == "importer_fidelity":
        print("importer_fidelity result: do not report as independent generation accuracy.")
    print(f"Report: {resolved_out}")

    if differential.verdict == "FAIL":
        raise SystemExit(2)
    if differential.verdict == "REVIEW_REQUIRED":
        raise SystemExit(3)


if __name__ == "__main__":
    main()
