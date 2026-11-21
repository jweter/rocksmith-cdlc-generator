"""CLI for copyright-free known-truth audio and independent external comparison."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .auto_cdlc_truth import KnownTruthError, generate_known_truth


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cdlc-auto-cdlc-truth",
        description=(
            "Generate a fully reproducible synthetic song with sample-exact "
            "ground truth, then compare external Bass MIDI/SVL or local analysis "
            "on absolute audio time without ever writing into Rocksmith."
        ),
    )
    commands = parser.add_subparsers(dest="command", required=True)
    generate = commands.add_parser("generate", help="Create an original synthetic WAV and verified truth sidecar")
    generate.add_argument("--out-dir", type=Path, required=True)
    compare = commands.add_parser("evaluate", help="Compare one or both engines to verified synthetic truth")
    compare.add_argument("--fixture-dir", type=Path, required=True)
    compare.add_argument("--upstream-dir", type=Path, help="Auto-cdlc .mid/.svl/diagnostico.json folder")
    compare.add_argument("--local-project", type=Path, help="Our project with original WAV + Bass/tempo analyses")
    compare.add_argument("--out", type=Path, required=True, help="Aggregate-only JSON outside checkout")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        if args.command == "generate":
            audio, truth = generate_known_truth(args.out_dir)
            print(f"Synthetic audio: {audio}")
            print(f"Verified truth: {truth}")
            return
        # Generate needs only the lightweight standard-library audio code. Do
        # not import mido or analysis engines until evaluation is requested.
        from .auto_cdlc_truth_benchmark import run_known_truth_benchmark

        result = run_known_truth_benchmark(
            args.fixture_dir,
            upstream_dir=args.upstream_dir,
            local_project=args.local_project,
            out_path=args.out,
        )
    except (KnownTruthError, ValueError, OSError) as exc:
        print(f"synthetic truth benchmark error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    print(f"Synthetic fixture comparison: {result['comparison_verdict']}")
    for name, metrics in result["engine_results"].items():
        print(f"  {name}: {metrics['fixture_verdict']} ({','.join(metrics['failure_reasons']) or 'no threshold errors'})")
    print("No real-song or gameplay readiness is implied.")
    raise SystemExit(0 if result["comparison_verdict"] == "PASS" else 2)


if __name__ == "__main__":
    main()
