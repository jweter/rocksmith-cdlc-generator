from __future__ import annotations

import argparse
from pathlib import Path

from rocksmith_cdlc_generator.tone_reference_decision import (
    build_review_decision,
    stage_accepted_components,
    write_review_decision,
)
from rocksmith_cdlc_generator.tone_reference_proposal import ToneReferenceReviewerProposal
from rocksmith_cdlc_generator.tone_review import load_tone_review, write_tone_review


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Record explicit human accept/reject decisions for a private tone-reference proposal "
            "and stage accepted observations into a still-pending tone review."
        )
    )
    parser.add_argument("proposal", type=Path, help="Private tone-reference proposal JSON")
    parser.add_argument("tone_review", type=Path, help="Existing pending human tone-review JSON")
    parser.add_argument("--accept", action="append", default=[], metavar="SLOT", help="Accept one proposed slot")
    parser.add_argument("--reject", action="append", default=[], metavar="SLOT", help="Reject one proposed slot")
    parser.add_argument("--note", help="Reviewer note recorded with each explicit decision")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("private/tone-reference-decisions"),
        help="Ignored private output directory (default: private/tone-reference-decisions)",
    )
    args = parser.parse_args()

    proposal = ToneReferenceReviewerProposal.model_validate_json(
        args.proposal.read_text(encoding="utf-8")
    )
    review = load_tone_review(args.tone_review)
    decision = build_review_decision(
        proposal,
        accept_slots=args.accept,
        reject_slots=args.reject,
        reviewer_note=args.note,
    )
    staged = stage_accepted_components(review, proposal, decision)

    stem = f"{proposal.arrangement}-{proposal.candidate_fingerprint[:12]}"
    decision_path = write_review_decision(decision, args.output_dir / f"{stem}-decision.json")
    staged_path = write_tone_review(staged, args.output_dir / f"{stem}-staged-tone-review.json")

    print(f"Decision artifact: {decision_path}")
    print(f"Staged tone review: {staged_path}")
    print("Final component approval required: yes")
    print("Automatic apply permitted: no")
    print("Injection permitted by this step: no")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
