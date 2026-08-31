from __future__ import annotations

from pathlib import Path

import pytest

from rocksmith_cdlc_generator.source_rights_cli import build_parser


def test_parser_accepts_explicit_local_rights_review() -> None:
    args = build_parser().parse_args(
        [
            "projects/song",
            "a" * 64,
            "--rights-class",
            "user_owned_local",
            "--note",
            "Owned local copy",
        ]
    )

    assert args.project == Path("projects/song")
    assert args.source_sha256 == "a" * 64
    assert args.rights_class == "user_owned_local"
    assert args.note == "Owned local copy"


@pytest.mark.parametrize("rights_class", ["unknown", "streaming_reference_only"])
def test_parser_does_not_offer_unresolved_or_reference_only_classes(rights_class: str) -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(
            ["projects/song", "a" * 64, "--rights-class", rights_class]
        )
