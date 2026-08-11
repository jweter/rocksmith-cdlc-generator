from __future__ import annotations

import argparse
from pathlib import Path

from rocksmith_cdlc_generator.tone_reference_audition_ack import ToneAuditionAcknowledgement
from rocksmith_cdlc_generator.tone_reference_final_ack import (
    ToneReferenceFinalReviewAcknowledgement,
)
from rocksmith_cdlc_generator.tone_reference_guarded_approval import (
    ComponentApprovalRequest,
    GuardedToneApprovalRequest,
    ToneApprovalPolicy,
    ToneApprovalRequest,
    guarded_final_tone_approval,
)
from rocksmith_cdlc_generator.tone_reference_review_diff import ToneReviewSettingsDiff
from rocksmith_cdlc_generator.tone_review import load_tone_review, write_tone_review


def _component(value: str) -> ComponentApprovalRequest:
    if ":" not in value:
        raise argparse.ArgumentTypeError("component approval must be ARRANGEMENT:FAMILY")
    arrangement, family = value.split(":", 1)
    if not arrangement.strip() or not family.strip():
        raise argparse.ArgumentTypeError("component approval must be ARRANGEMENT:FAMILY")
    return ComponentApprovalRequest(arrangement=arrangement.strip(), family=family.strip())


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Execute explicit final tone approvals only against current human review gates."
    )
    parser.add_argument("original_review", type=Path)
    parser.add_argument("staged_review", type=Path)
    parser.add_argument("staged_diff", type=Path)
    parser.add_argument("acknowledgement", type=Path)
    parser.add_argument("--approve-component", action="append", type=_component, default=[])
    parser.add_argument("--approve-tone", action="append", default=[])
    parser.add_argument(
        "--require-audition",
        action="store_true",
        help="Require a current positive human listening acknowledgement before approval.",
    )
    parser.add_argument(
        "--audition-acknowledgement",
        type=Path,
        help="Tone audition acknowledgement bound to the exact staged settings diff.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("private/final-tone-reviews/guarded-final-tone-review.json"),
        help="Ignored private output path for the resulting review artifact.",
    )
    args = parser.parse_args()

    if args.require_audition and args.audition_acknowledgement is None:
        parser.error("--require-audition requires --audition-acknowledgement")

    original = load_tone_review(args.original_review)
    staged = load_tone_review(args.staged_review)
    diff = ToneReviewSettingsDiff.model_validate_json(args.staged_diff.read_text(encoding="utf-8"))
    acknowledgement = ToneReferenceFinalReviewAcknowledgement.model_validate_json(
        args.acknowledgement.read_text(encoding="utf-8")
    )
    audition = None
    if args.audition_acknowledgement is not None:
        audition = ToneAuditionAcknowledgement.model_validate_json(
            args.audition_acknowledgement.read_text(encoding="utf-8")
        )
    request = GuardedToneApprovalRequest(
        component_approvals=args.approve_component,
        tone_approvals=[ToneApprovalRequest(arrangement=item) for item in args.approve_tone],
    )

    approved = guarded_final_tone_approval(
        original,
        staged,
        diff,
        acknowledgement,
        request,
        policy=ToneApprovalPolicy(require_current_audition=args.require_audition),
        audition_acknowledgement=audition,
    )
    write_tone_review(approved, args.output)
    print(f"Guarded review artifact: {args.output}")
    print(f"Audition required: {'yes' if args.require_audition else 'no'}")
    print(f"Ready for injection: {'yes' if approved.ready_for_injection else 'no'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
