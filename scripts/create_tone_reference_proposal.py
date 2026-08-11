from __future__ import annotations

import argparse
from pathlib import Path

from rocksmith_cdlc_generator.tone_reference_proposal import (
    build_reviewer_proposal,
    write_reviewer_proposal,
)
from rocksmith_cdlc_generator.tone_reference_recommendations import ToneRecommendationEvidenceReport


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Stage selected local tone evidence into a separate unapproved reviewer proposal."
    )
    parser.add_argument("evidence", type=Path, help="Private tone-reference evidence JSON")
    parser.add_argument("--arrangement", required=True, choices=["lead", "rhythm", "bass"])
    parser.add_argument("--fingerprint", required=True, help="Candidate tone fingerprint from the evidence report")
    parser.add_argument(
        "--slot",
        action="append",
        dest="slots",
        help="Component slot to stage; repeat for multiple slots. Omit to stage all candidate components.",
    )
    parser.add_argument("--note", help="Optional reviewer note")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("private/tone-reference-proposals/proposal.json"),
        help="Ignored private proposal path",
    )
    args = parser.parse_args()

    report = ToneRecommendationEvidenceReport.model_validate_json(
        args.evidence.read_text(encoding="utf-8")
    )
    proposal = build_reviewer_proposal(
        report,
        arrangement=args.arrangement,
        candidate_fingerprint=args.fingerprint,
        component_slots=args.slots,
        reviewer_note=args.note,
    )
    path = write_reviewer_proposal(proposal, args.output)

    print(f"Reviewer proposal: {path}")
    print("Approved: no")
    print("Automatic apply permitted: no")
    print("Injection permitted: no")
    print("Human review required: yes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
