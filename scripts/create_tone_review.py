from __future__ import annotations

import argparse
from pathlib import Path

from rocksmith_cdlc_generator.tone_catalog import BoundRocksmithTonePlan
from rocksmith_cdlc_generator.tone_review import create_tone_review, write_tone_review


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a human-review artifact from a bound Rocksmith tone plan.")
    parser.add_argument("plan", type=Path, help="Bound tone-plan JSON")
    parser.add_argument("output", type=Path, help="Review artifact JSON")
    args = parser.parse_args()

    plan = BoundRocksmithTonePlan.model_validate_json(args.plan.read_text(encoding="utf-8"))
    review = create_tone_review(plan)
    path = write_tone_review(review, args.output)
    print(path)
    print(review.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
