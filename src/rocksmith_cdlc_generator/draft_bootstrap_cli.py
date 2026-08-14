from __future__ import annotations

import argparse
import json
from pathlib import Path

from .draft_bootstrap import DraftBootstrapError, create_and_run_first_draft
from .source_intake import SourceRightsClass


_RIGHTS_CHOICES = [
    "unknown",
    "user_owned_local",
    "licensed_download",
    "creative_commons",
    "public_domain",
    "self_recorded",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cdlc-draft",
        description="Create a Bass project from local sources and run every safe deterministic first-draft stage.",
    )
    parser.add_argument("audio", type=Path, help="Local recording audio")
    parser.add_argument("--title", help="Song title; defaults to the audio filename stem")
    parser.add_argument("--artist")
    parser.add_argument("--notation", type=Path, help="Optional local MIDI/GP3-5/MusicXML/MXL/PSARC source")
    parser.add_argument("--projects-root", type=Path, default=Path("projects"))
    parser.add_argument("--rights-class", choices=_RIGHTS_CHOICES, default="unknown")
    parser.add_argument("--license-note")
    parser.add_argument("--notation-rights-class", choices=_RIGHTS_CHOICES, default="unknown")
    parser.add_argument("--notation-license-note")
    parser.add_argument("--track-index", type=int, help="Explicit MIDI/Guitar Pro track index when needed")
    parser.add_argument("--part-index", type=int, help="Explicit MusicXML part index when needed")
    parser.add_argument("--bridge", type=Path, help="Optional PSARC bridge executable/DLL")
    parser.add_argument("--max-steps", type=int, default=8)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        result = create_and_run_first_draft(
            args.audio,
            title=args.title,
            artist=args.artist,
            notation=args.notation,
            projects_root=args.projects_root,
            audio_rights_class=SourceRightsClass(args.rights_class),
            audio_license_note=args.license_note,
            notation_rights_class=SourceRightsClass(args.notation_rights_class),
            notation_license_note=args.notation_license_note,
            track_index=args.track_index,
            part_index=args.part_index,
            bridge_path=args.bridge,
            max_steps=args.max_steps,
        )
    except DraftBootstrapError as exc:
        print(
            json.dumps(
                {
                    "status": "error",
                    "stage": exc.stage,
                    "message": str(exc),
                    "project_path": exc.project_path,
                },
                indent=2,
            )
        )
        raise SystemExit(1) from exc

    print(result.model_dump_json(indent=2))
    if result.automatic_run.stop_reason in {"step_failed", "no_progress"}:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
