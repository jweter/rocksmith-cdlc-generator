from __future__ import annotations

import argparse
from pathlib import Path

from .project_source_inventory import build_project_source_inventory


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cdlc-sources",
        description="Show local source, reference, provenance, and adapter readiness for a CDLC project",
    )
    parser.add_argument("project", type=Path)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    inventory = build_project_source_inventory(args.project)
    print(inventory.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
