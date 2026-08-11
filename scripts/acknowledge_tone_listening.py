from __future__ import annotations

import argparse
from pathlib import Path

from rocksmith_cdlc_generator.tone_audition_ack import acknowledge_tone_listening
from rocksmith_cdlc_generator.tone_reference_review_diff import ToneReviewSettingsDiff


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Record human listening provenance for one exact staged tone-settings diff."
    )
    parser.add_argument("--staged-diff", type=Path, required=True)
    parser.add_argument("--reviewer", required=True)
    parser.add_argument(
        "--audition-method",
        choices=["live_instrument", "private_di_replay", "external_preview"],
        required=True,
    )
    parser.add_argument("--arrangement", action="append", required=True)
    parser.add_argument(
        "--decision",
        choices=["rejected", "keep_editing", "continue_to_review"],
        required=True,
    )
    parser.add_argument("--reviewer-note")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("private/tone-listening-acknowledgements/tone-listening-ack.json"),
    )
    args = parser.parse_args()

    report = ToneReviewSettingsDiff.model_validate_json(args.staged_diff.read_text(encoding="utf-8"))
    acknowledgement = acknowledge_tone_listening(
        report,
        reviewer=args.reviewer,
        audition_method=args.audition_method,
        arrangements=args.arrangement,
        decision=args.decision,
        reviewer_note=args.reviewer_note,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(acknowledgement.model_dump_json(indent=2), encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
