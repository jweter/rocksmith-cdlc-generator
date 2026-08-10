from __future__ import annotations

import argparse
from pathlib import Path

from rocksmith_cdlc_generator.benchmark import (
    evaluate_chart,
    read_benchmark_chart,
    summarize_suite,
    write_benchmark_report,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare benchmark reference charts against generated predictions."
    )
    parser.add_argument(
        "--reference",
        action="append",
        required=True,
        type=Path,
        help="Reference BenchmarkChart JSON. Repeat once per case.",
    )
    parser.add_argument(
        "--predicted",
        action="append",
        required=True,
        type=Path,
        help="Predicted BenchmarkChart JSON. Repeat once per case, in reference order.",
    )
    parser.add_argument(
        "--onset-tolerance",
        type=float,
        default=0.12,
        help="Maximum onset difference in seconds for an exact-pitch note match (default: 0.12).",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Destination JSON report. A Markdown sibling is also written.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if len(args.reference) != len(args.predicted):
        raise SystemExit("--reference and --predicted must be supplied the same number of times")

    cases = []
    for reference_path, predicted_path in zip(args.reference, args.predicted, strict=True):
        reference = read_benchmark_chart(reference_path)
        predicted = read_benchmark_chart(predicted_path)
        cases.append(
            evaluate_chart(
                reference,
                predicted,
                onset_tolerance_seconds=args.onset_tolerance,
            )
        )

    report = summarize_suite(cases)
    output = write_benchmark_report(report, args.output)
    print(output)
    print(output.with_suffix(".md"))


if __name__ == "__main__":
    main()
