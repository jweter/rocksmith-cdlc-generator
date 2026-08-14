from __future__ import annotations

import argparse
from pathlib import Path

from .source_intake import SourceRightsClass
from .source_rights_review import record_source_rights_review


_REVIEWABLE_RIGHTS = [
    SourceRightsClass.user_owned_local.value,
    SourceRightsClass.licensed_download.value,
    SourceRightsClass.creative_commons.value,
    SourceRightsClass.public_domain.value,
    SourceRightsClass.self_recorded.value,
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cdlc-source-rights",
        description="Record an explicit human rights/provenance review for a known local project source",
    )
    parser.add_argument("project", type=Path)
    parser.add_argument("source_sha256", help="SHA-256 shown by `cdlc-sources PROJECT`")
    parser.add_argument("--rights-class", required=True, choices=_REVIEWABLE_RIGHTS)
    parser.add_argument("--note", help="Optional provenance/license review note")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    output = record_source_rights_review(
        args.project,
        source_sha256=args.source_sha256,
        rights_class=SourceRightsClass(args.rights_class),
        note=args.note,
    )
    print(output)


if __name__ == "__main__":
    main()
