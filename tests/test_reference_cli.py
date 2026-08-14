from __future__ import annotations

import json
from pathlib import Path

from rocksmith_cdlc_generator.reference_cli import build_parser, main
from rocksmith_cdlc_generator.reference_sources import ReferenceSourceRecord
from rocksmith_cdlc_generator.source_intake import describe_streaming_reference


def test_reference_cli_parser_add() -> None:
    args = build_parser().parse_args(
        [
            "add",
            "projects/song",
            "https://www.youtube.com/watch?v=abc123",
            "--name",
            "Official studio upload",
            "--provider",
            "YouTube",
            "--version",
            "2011 remaster",
        ]
    )

    assert args.command == "add"
    assert args.display_name == "Official studio upload"
    assert args.provider == "YouTube"
    assert args.version_hint == "2011 remaster"


def test_reference_cli_add_delegates_without_media_access(monkeypatch, capsys) -> None:
    captured: dict[str, object] = {}

    def fake_add(project, **kwargs):
        captured["project"] = project
        captured.update(kwargs)
        return Path("projects/song/sources/references/reference-test.json")

    monkeypatch.setattr("rocksmith_cdlc_generator.reference_cli.add_reference_source", fake_add)
    monkeypatch.setattr(
        "sys.argv",
        [
            "cdlc-reference",
            "add",
            "projects/song",
            "https://www.youtube.com/watch?v=abc123",
            "--name",
            "Official upload",
            "--provider",
            "YouTube",
        ],
    )

    main()

    assert captured["url"] == "https://www.youtube.com/watch?v=abc123"
    assert captured["display_name"] == "Official upload"
    assert captured["provider"] == "YouTube"
    assert "reference-test.json" in capsys.readouterr().out


def test_reference_cli_list_emits_reference_only_json(monkeypatch, capsys) -> None:
    record = ReferenceSourceRecord(
        descriptor=describe_streaming_reference(
            "https://www.youtube.com/watch?v=abc123",
            display_name="Official upload",
        ),
        provider="YouTube",
        version_hint="studio",
    )
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.reference_cli.load_reference_sources",
        lambda project: [record],
    )
    monkeypatch.setattr("sys.argv", ["cdlc-reference", "list", "projects/song"])

    main()

    payload = json.loads(capsys.readouterr().out)
    assert payload[0]["descriptor"]["rights_class"] == "streaming_reference_only"
    assert payload[0]["descriptor"]["local_bytes_available"] is False
    assert payload[0]["provider"] == "YouTube"
