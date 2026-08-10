from __future__ import annotations

import argparse
import json
from pathlib import Path

from .models import ProjectManifest
from .project import create_project, normalize_project


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cdlc", description="Rocksmith CDLC Generator")
    sub = parser.add_subparsers(dest="command", required=True)

    new = sub.add_parser("new", help="Create a project from source audio")
    new.add_argument("--audio", required=True, type=Path)
    new.add_argument("--artist")
    new.add_argument("--title", required=True)
    new.add_argument("--instrument", action="append", dest="instruments", choices=["bass", "lead", "rhythm"], default=None)
    new.add_argument("--projects-root", type=Path, default=Path("projects"))

    normalize = sub.add_parser("normalize", help="Create canonical working WAV")
    normalize.add_argument("project", type=Path)

    inspect = sub.add_parser("inspect", help="Print project manifest")
    inspect.add_argument("project", type=Path)
    return parser


def main() -> None:
    args = build_parser().parse_args()

    if args.command == "new":
        project = create_project(
            audio=args.audio,
            projects_root=args.projects_root,
            artist=args.artist,
            title=args.title,
            instruments=args.instruments or ["bass"],
        )
        print(project)
        return

    if args.command == "normalize":
        print(normalize_project(args.project))
        return

    if args.command == "inspect":
        manifest = ProjectManifest.load(args.project.resolve())
        print(json.dumps(manifest.model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    main()
