from __future__ import annotations

import argparse
from pathlib import Path

from rocksmith_cdlc_generator.rocksmith_tone_mapping import map_tone_hypothesis
from rocksmith_cdlc_generator.tone_research import ToneRigHypothesis


def main() -> None:
    parser = argparse.ArgumentParser(description="Map a researched tone hypothesis into conservative Rocksmith tone families")
    parser.add_argument("hypothesis", type=Path, help="ToneRigHypothesis JSON")
    parser.add_argument("--arrangement", action="append", choices=["lead", "rhythm", "bass"], required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--minimum-effect-support", type=float, default=0.35)
    args = parser.parse_args()

    hypothesis = ToneRigHypothesis.model_validate_json(args.hypothesis.read_text(encoding="utf-8"))
    plan = map_tone_hypothesis(
        hypothesis,
        arrangements=args.arrangement,
        minimum_effect_support=args.minimum_effect_support,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    print(args.output)
    print(plan.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
