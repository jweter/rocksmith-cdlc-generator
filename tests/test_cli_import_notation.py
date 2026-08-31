from __future__ import annotations

from pathlib import Path

from rocksmith_cdlc_generator.cli import build_parser


def test_import_notation_cli_parses_required_arguments() -> None:
    args = build_parser().parse_args(
        [
            "import-notation",
            "projects/song",
            "--fixture",
            "page1.json",
            "--title",
            "Test Song",
            "--artist",
            "Test Artist",
        ]
    )

    assert args.command == "import-notation"
    assert args.project == Path("projects/song")
    assert args.fixture == Path("page1.json")
    assert args.title == "Test Song"
    assert args.artist == "Test Artist"
    assert args.page_image is None
    assert args.count_in_measures == 2
    assert args.subdivision == "none"


def test_import_notation_cli_parses_optional_arguments() -> None:
    args = build_parser().parse_args(
        [
            "import-notation",
            "projects/song",
            "--fixture",
            "page1.json",
            "--title",
            "Test Song",
            "--artist",
            "Test Artist",
            "--page-image",
            "page1.png",
            "--count-in-measures",
            "1",
            "--subdivision",
            "eighth",
        ]
    )

    assert args.page_image == Path("page1.png")
    assert args.count_in_measures == 1
    assert args.subdivision == "eighth"
