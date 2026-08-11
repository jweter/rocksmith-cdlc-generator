from __future__ import annotations

import argparse
from pathlib import Path

from rocksmith_cdlc_generator.tone_catalog import BoundRocksmithTonePlan
from rocksmith_cdlc_generator.tone_reference_library import read_library
from rocksmith_cdlc_generator.tone_reference_recommendations import build_tone_reference_evidence
from rocksmith_cdlc_generator.tone_reference_report import write_tone_reference_report_bundle


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create private, human-review-only local tone recommendation evidence."
    )
    parser.add_argument("bound_plan", type=Path, help="Bound Rocksmith tone-plan JSON")
    parser.add_argument("library", type=Path, help="Private local tone-reference library JSON")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("private/tone-reference-evidence"),
        help="Ignored private output directory (default: private/tone-reference-evidence)",
    )
    parser.add_argument("--limit", type=int, default=5, help="Maximum candidates per arrangement")
    parser.add_argument("--stem", help="Optional output filename stem")
    args = parser.parse_args()

    if args.limit < 1:
        parser.error("--limit must be at least 1")

    plan = BoundRocksmithTonePlan.model_validate_json(args.bound_plan.read_text(encoding="utf-8"))
    library = read_library(args.library)
    report = build_tone_reference_evidence(plan, library, limit_per_arrangement=args.limit)
    json_path, markdown_path = write_tone_reference_report_bundle(
        report,
        args.output_dir,
        stem=args.stem,
    )

    print(f"JSON evidence: {json_path}")
    print(f"Reviewer report: {markdown_path}")
    print("Human review required: yes")
    print("Automatic apply permitted: no")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
