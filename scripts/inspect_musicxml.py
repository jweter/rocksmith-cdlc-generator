from __future__ import annotations

import argparse
from pathlib import Path

from rocksmith_cdlc_generator.musicxml_inspection import inspect_musicxml_source


def _format_tuning(values: list[int] | None) -> str:
    if not values:
        return "unknown"
    return ",".join(str(value) for value in values)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect a local Guitar Pro MusicXML export before importing Lead, Rhythm, or Bass. "
            "The source file is read only and is not copied into the repository."
        )
    )
    parser.add_argument("musicxml", type=Path)
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the complete machine-readable inspection JSON instead of the summary table.",
    )
    args = parser.parse_args()

    report = inspect_musicxml_source(args.musicxml)
    if args.json:
        print(report.model_dump_json(indent=2))
        return 0

    print(f"MusicXML source: {report.source_filename}")
    print(f"SHA-256: {report.source_sha256}")
    print("\nParts:")
    print("idx  name                         notes  measures  tuning                  lead rhythm bass")
    print("---  ---------------------------  -----  --------  ----------------------  ---- ------ ----")
    for part in report.parts:
        name = part.name[:27]
        print(
            f"{part.part_index:>3}  {name:<27}  {part.pitched_note_count:>5}  "
            f"{part.measure_count:>8}  {_format_tuning(part.tuning_midi):<22}  "
            f"{part.lead_score:>4} {part.rhythm_score:>6} {part.bass_score:>4}"
        )

    print("\nUse the part index with:")
    print(
        "  cdlc import-musicxml PROJECT --musicxml FILE --instrument lead|rhythm|bass --part-index N"
    )
    print("Positive role scores are hints only; inspect the track name/tuning and choose explicitly when unsure.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
