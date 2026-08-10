from pathlib import Path

from rocksmith_cdlc_generator.cli import build_parser


def test_identify_metadata_cli_defaults() -> None:
    args = build_parser().parse_args(["identify-metadata", "project"])
    assert args.command == "identify-metadata"
    assert args.project == Path("project")
    assert args.limit == 5
    assert args.refresh is False


def test_select_metadata_cli_requires_report_and_index() -> None:
    args = build_parser().parse_args(
        [
            "select-metadata",
            "project",
            "--report",
            "project/metadata/musicbrainz.json",
            "--index",
            "2",
        ]
    )
    assert args.command == "select-metadata"
    assert args.index == 2


def test_prepare_dlcbuilder_allows_reviewed_metadata_fallback() -> None:
    args = build_parser().parse_args(
        [
            "prepare-dlcbuilder",
            "project",
            "--cover",
            "cover.png",
        ]
    )
    assert args.album is None
    assert args.year is None
    assert args.cover == Path("cover.png")


def test_prepare_dlcbuilder_explicit_metadata_is_still_supported() -> None:
    args = build_parser().parse_args(
        [
            "prepare-dlcbuilder",
            "project",
            "--album",
            "Album",
            "--year",
            "2001",
            "--cover",
            "cover.png",
        ]
    )
    assert args.album == "Album"
    assert args.year == 2001
