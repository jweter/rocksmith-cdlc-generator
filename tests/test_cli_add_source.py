from __future__ import annotations

from pathlib import Path

from rocksmith_cdlc_generator.cli import build_parser


def test_add_source_cli_accepts_unified_routing_options() -> None:
    args = build_parser().parse_args(
        [
            "add-source",
            "score.gp5",
            "--project",
            "projects/song",
            "--instrument",
            "rhythm",
            "--track-index",
            "2",
            "--rights-class",
            "user_owned_local",
        ]
    )

    assert args.command == "add-source"
    assert args.source == Path("score.gp5")
    assert args.project == Path("projects/song")
    assert args.instrument == "rhythm"
    assert args.track_index == 2
    assert args.rights_class == "user_owned_local"


def test_add_source_cli_does_not_offer_streaming_reference_as_local_rights_class() -> None:
    parser = build_parser()
    try:
        parser.parse_args(
            [
                "add-source",
                "song.mp3",
                "--title",
                "Song",
                "--rights-class",
                "streaming_reference_only",
            ]
        )
    except SystemExit as exc:
        assert exc.code == 2
    else:  # pragma: no cover - argparse must reject this local-byte classification.
        raise AssertionError("streaming_reference_only unexpectedly accepted by add-source")
