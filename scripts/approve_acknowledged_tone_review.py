from __future__ import annotations

import argparse
from pathlib import Path

from rocksmith_cdlc_generator.tone_reference_final_ack import ToneReferenceFinalReviewAcknowledgement
from rocksmith_cdlc_generator.tone_reference_guarded_approval import approve_acknowledged_staged_review
from rocksmith_cdlc_generator.tone_reference_review_diff import ToneReviewSettingsDiff
from rocksmith_cdlc_generator.tone_review import load_tone_review, write_tone_review

CONFIRMATION = "APPROVE-ACKNOWLEDGED-TONE-SETTINGS"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Explicitly approve the exact staged tone settings covered by a current human "
            "review acknowledgement. This command refuses stale acknowledgements and does not "
            "permit setting changes during approval."
        )
    )
    parser.add_argument("--original-review", type=Path, required=True)
    parser.add_argument("--staged-review", type=Path, required=True)
    parser.add_argument("--staged-diff", type=Path, required=True)
    parser.add_argument("--acknowledgement", type=Path, required=True)
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--reviewer-note")
    parser.add_argument(
        "--confirm",
        required=True,
        help=f"Must be exactly {CONFIRMATION!r}.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("private/tone-reference-approved"),
    )
    args = parser.parse_args()

    if args.confirm != CONFIRMATION:
        parser.error(f"--confirm must be exactly {CONFIRMATION!r}")

    original = load_tone_review(args.original_review)
    staged = load_tone_review(args.staged_review)
    report = ToneReviewSettingsDiff.model_validate_json(args.staged_diff.read_text(encoding="utf-8"))
    acknowledgement = ToneReferenceFinalReviewAcknowledgement.model_validate_json(
        args.acknowledgement.read_text(encoding="utf-8")
    )

    approved, receipt = approve_acknowledged_staged_review(
        original,
        staged,
        report,
        acknowledgement,
        reviewer=args.reviewer,
        confirm_approval=True,
        reviewer_note=args.reviewer_note,
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    approved_path = args.output_dir / "approved-tone-review.json"
    receipt_path = args.output_dir / "guarded-approval-receipt.json"
    write_tone_review(approved, approved_path)
    receipt_path.write_text(receipt.model_dump_json(indent=2), encoding="utf-8")

    print(f"Approved review: {approved_path}")
    print(f"Approval receipt: {receipt_path}")
    print("ready_for_injection=true; downstream serialization must still validate provenance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
