from __future__ import annotations

import json
from pathlib import Path

from rocksmith_cdlc_generator.recording_context import ReviewedRecordingContext
from rocksmith_cdlc_generator.reference_cli import build_parser, main
from rocksmith_cdlc_generator.reference_selection import ReferenceSelection


def test_reference_cli_parser_context_commands() -> None:
    context = build_parser().parse_args(["context", "projects/song"])
    show = build_parser().parse_args(["show-context", "projects/song"])

    assert context.command == "context"
    assert show.command == "show-context"


def test_reference_cli_context_delegates_build(monkeypatch, capsys) -> None:
    output = Path("projects/song/metadata/recording_context.json")
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.reference_cli.build_reviewed_recording_context",
        lambda project: output,
    )
    monkeypatch.setattr("sys.argv", ["cdlc-reference", "context", "projects/song"])

    main()

    assert "recording_context.json" in capsys.readouterr().out


def test_reference_cli_show_context_emits_json(monkeypatch, capsys) -> None:
    context = ReviewedRecordingContext(
        reference_selection=ReferenceSelection(
            reference_url="https://www.youtube.com/watch?v=abc123",
            display_name="Official upload",
            provider="YouTube",
            version_hint="studio",
        )
    )
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.reference_cli.load_reviewed_recording_context",
        lambda project: context,
    )
    monkeypatch.setattr("sys.argv", ["cdlc-reference", "show-context", "projects/song"])

    main()

    payload = json.loads(capsys.readouterr().out)
    assert payload["reference_selection"]["human_confirmed"] is True
    assert payload["reference_selection"]["provider"] == "YouTube"
    assert payload["selected_metadata"] is None
