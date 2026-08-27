from __future__ import annotations

from rocksmith_cdlc_generator.eof_cli import build_parser


def test_parser_accepts_alternate_score_comparison() -> None:
    args = build_parser().parse_args(["project", "--compare-score", "alternate.gp5"])
    assert str(args.project) == "project"
    assert str(args.compare_score) == "alternate.gp5"
