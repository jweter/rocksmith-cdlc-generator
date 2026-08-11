from __future__ import annotations

import argparse
from pathlib import Path

from rocksmith_cdlc_generator.tone_reference_final_ack import (
    acknowledge_staged_settings_diff,
    write_final_review_acknowledgement,
)
from rocksmith_cdlc_generator.tone_reference_review_diff import ToneReviewSettingsDiff


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Record a human acknowledgement of one exact staged tone-settings diff."
    )
    parser.add_argument("diff", type=Path, help="Private staged tone-settings diff JSON")
    parser.add_argument("--reviewer", required=True, help="Reviewer identity recorded in the acknowledgement")
    parser.add_argument("--note", help="Optional reviewer note")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("private/tone-reference-acknowledgements/final-review-ack.json"),
        help="Ignored private output path",
    )
    args = parser.parse_args()

    report = ToneReviewSettingsDiff.model_validate_json(args.diff.read_text(encoding="utf-8"))
    acknowledgement = acknowledge_staged_settings_diff(
        report,
        reviewer=args.reviewer,
        reviewer_note=args.note,
    )
    path = write_final_review_acknowledgement(acknowledgement, args.output)
    print(f"Final review acknowledgement: {path}")
    print(f"Reviewer: {acknowledgement.reviewer}")
    print("Component/tone approval granted: no")
    print("Injection permitted: no")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
