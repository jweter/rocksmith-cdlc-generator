from __future__ import annotations

import argparse
from pathlib import Path

from rocksmith_cdlc_generator.tone_reference_audition_ack import (
    acknowledge_tone_audition,
    write_tone_audition_acknowledgement,
)
from rocksmith_cdlc_generator.tone_reference_review_diff import ToneReviewSettingsDiff


def main() -> None:
    parser = argparse.ArgumentParser(description="Record a human listening decision for one staged tone diff.")
    parser.add_argument("diff", type=Path)
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--decision", choices=["sounds_right", "needs_revision"], required=True)
    parser.add_argument("--method", required=True, help="How the tone was auditioned, e.g. Scarlett 2i2 live monitor")
    parser.add_argument("--note")
    parser.add_argument("--output", type=Path, default=Path("private/tone-audition-acknowledgements/acknowledgement.json"))
    args = parser.parse_args()

    report = ToneReviewSettingsDiff.model_validate_json(args.diff.read_text(encoding="utf-8"))
    acknowledgement = acknowledge_tone_audition(
        report,
        reviewer=args.reviewer,
        decision=args.decision,
        audition_method=args.method,
        reviewer_note=args.note,
    )
    write_tone_audition_acknowledgement(acknowledgement, args.output)
    print(args.output)


if __name__ == "__main__":
    main()
