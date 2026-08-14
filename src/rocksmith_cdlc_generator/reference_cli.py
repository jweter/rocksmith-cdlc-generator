from __future__ import annotations

import argparse
import json
from pathlib import Path

from .reference_selection import load_reference_selection, select_reference_source
from .reference_sources import add_reference_source, load_reference_sources


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cdlc-reference",
        description="Manage reference-only streaming/video source metadata without downloading media",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add", help="Record one public reference URL for version/discovery evidence")
    add.add_argument("project", type=Path)
    add.add_argument("url", help="Public HTTP(S) reference URL; media is never downloaded")
    add.add_argument("--name", required=True, dest="display_name", help="Human-readable reference name")
    add.add_argument("--provider", help="Optional provider label such as YouTube")
    add.add_argument("--version", dest="version_hint", help="Optional version/remaster/live/studio hint")
    add.add_argument("--notes", help="Optional human review notes")

    list_cmd = sub.add_parser("list", help="List persisted reference-only sources for a project")
    list_cmd.add_argument("project", type=Path)

    select = sub.add_parser(
        "select",
        help="Explicitly confirm one registered reference as the intended recording/version evidence",
    )
    select.add_argument("project", type=Path)
    select.add_argument("url", help="Exact URL of an already registered project reference")
    select.add_argument(
        "--note",
        dest="confirmation_note",
        help="Optional human note explaining why this studio/live/remaster version was selected",
    )

    selected = sub.add_parser("selected", help="Show the explicitly selected recording/version reference")
    selected.add_argument("project", type=Path)

    return parser


def main() -> None:
    args = build_parser().parse_args()

    if args.command == "add":
        path = add_reference_source(
            args.project,
            url=args.url,
            display_name=args.display_name,
            provider=args.provider,
            version_hint=args.version_hint,
            notes=args.notes,
        )
        print(path)
        return

    if args.command == "list":
        records = load_reference_sources(args.project)
        print(json.dumps([record.model_dump(mode="json") for record in records], indent=2))
        return

    if args.command == "select":
        print(
            select_reference_source(
                args.project,
                url=args.url,
                confirmation_note=args.confirmation_note,
            )
        )
        return

    if args.command == "selected":
        selection = load_reference_selection(args.project)
        print(json.dumps(None if selection is None else selection.model_dump(mode="json"), indent=2))
        return

    raise SystemExit(f"Unsupported command: {args.command}")  # pragma: no cover


if __name__ == "__main__":
    main()
