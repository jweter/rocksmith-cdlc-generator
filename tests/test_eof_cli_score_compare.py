from __future__ import annotations

from rocksmith_cdlc_generator.eof_cli import build_parser


def test_parser_accepts_alternate_score_comparison() -> None:
    args = build_parser().parse_args(["project", "--compare-score", "alternate.gp5"])
    assert str(args.project) == "project"
    assert str(args.compare_score) == "alternate.gp5"


def test_parser_accepts_short_note_truncation_check() -> None:
    args = build_parser().parse_args(["project", "--check-short-note-truncation"])
    assert str(args.project) == "project"
    assert args.check_short_note_truncation is True
