"""Opt-in, model-free-by-default Bass source evidence comparison CLI."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .bass_evidence_comparison import (
    BassEvidenceBenchmarkError,
    compare_bass_evidence_sources,
)
from .auto_cdlc_truth import KnownTruthError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cdlc-bass-evidence-compare",
        description=(
            "Compare original, already prepared frequency-focused and verified Bass "
            "stem audio to reproducible synthetic truth. Without --execute only "
            "inspect readiness. Never download models, separate sources, touch "
            "Rocksmith, or modify song charts."
        ),
    )
    parser.add_argument("--fixture-dir", required=True, type=Path)
    parser.add_argument("--project-dir", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--focused-wav", type=Path, help="Existing private focused artifact with matching hash receipt")
    parser.add_argument("--execute", action="store_true", help="Opt in to resource-admitted local pYIN scoring")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        report = compare_bass_evidence_sources(
            args.fixture_dir,
            args.project_dir,
            args.out,
            focused_path=args.focused_wav,
            execute=args.execute,
        )
    except (KnownTruthError, BassEvidenceBenchmarkError, ValueError, OSError) as exc:
        # Do not leak private absolute audio paths in CLI errors.
        print("Bass comparison refused: invalid fixture, source, or output boundary", file=sys.stderr)
        raise SystemExit(2) from exc
    print("Bass A/B comparison: " + report["comparison_verdict"])
    for mode, result in report["source_results"].items():
        print(f"  {mode}: {result['status']} / {result['reason']}")
    print("This is synthetic-clock evidence only; no instrument isolation, real-song, or gameplay PASS.")
    raise SystemExit(0 if report["comparison_verdict"] in {"READINESS_ONLY", "COMPARISON_SCORED"} else 2)


if __name__ == "__main__":
    main()
