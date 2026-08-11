from __future__ import annotations

import argparse
from pathlib import Path

from rocksmith_cdlc_generator.tone_reference_review_diff import (
    build_staged_settings_diff,
    write_staged_settings_diff_bundle,
)
from rocksmith_cdlc_generator.tone_review import load_tone_review


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare original and staged pending tone reviews for final human inspection."
    )
    parser.add_argument("original_review", type=Path, help="Original pending tone-review JSON")
    parser.add_argument("staged_review", type=Path, help="Staged pending tone-review JSON")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("private/tone-reference-diffs"),
        help="Ignored private output directory (default: private/tone-reference-diffs)",
    )
    parser.add_argument("--stem", help="Optional output filename stem")
    args = parser.parse_args()

    original = load_tone_review(args.original_review)
    staged = load_tone_review(args.staged_review)
    report = build_staged_settings_diff(original, staged)
    json_path, markdown_path = write_staged_settings_diff_bundle(
        report,
        args.output_dir,
        stem=args.stem,
    )

    print(f"JSON diff: {json_path}")
    print(f"Reviewer diff: {markdown_path}")
    print(f"Changed components: {len(report.changes)}")
    print("Human approval still required: yes")
    print("Automatic approval permitted: no")
    print("Injection permitted by this artifact: no")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
