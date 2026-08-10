from __future__ import annotations

import argparse
from pathlib import Path

from rocksmith_cdlc_generator.tone_research import SongIdentity, build_tone_research_plan


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a source-ranked web research plan for Rocksmith tone reconstruction")
    parser.add_argument("--artist", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--album")
    parser.add_argument("--year", type=int)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    plan = build_tone_research_plan(
        SongIdentity(artist=args.artist, title=args.title, album=args.album, year=args.year)
    )
    payload = plan.model_dump_json(indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
        print(args.output)
    else:
        print(payload)


if __name__ == "__main__":
    main()
