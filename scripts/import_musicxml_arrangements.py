from __future__ import annotations

import argparse
from pathlib import Path

from rocksmith_cdlc_generator.musicxml_multi_import import (
    MusicXMLArrangementSelection,
    import_project_musicxml_arrangements,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import explicitly selected Lead/Rhythm/Bass parts from one MusicXML score."
    )
    parser.add_argument("project", type=Path)
    parser.add_argument("musicxml", type=Path)
    parser.add_argument("--lead-part", type=int)
    parser.add_argument("--rhythm-part", type=int)
    parser.add_argument("--bass-part", type=int)
    args = parser.parse_args()

    selections = []
    for instrument, index in (
        ("lead", args.lead_part),
        ("rhythm", args.rhythm_part),
        ("bass", args.bass_part),
    ):
        if index is not None:
            selections.append(
                MusicXMLArrangementSelection(instrument=instrument, part_index=index)
            )

    result = import_project_musicxml_arrangements(
        args.project,
        args.musicxml,
        selections=selections,
    )
    print(result.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
