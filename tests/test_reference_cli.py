from __future__ import annotations

import json
from pathlib import Path

from rocksmith_cdlc_generator.reference_cli import build_parser, main
from rocksmith_cdlc_generator.reference_selection import ReferenceSelection
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


def test_reference_cli_parser_select_requires_registered_url() -> None:
    args = build_parser().parse_args(
        [
            "select",
            "projects/song",
            "https://www.youtube.com/watch?v=abc123",
            "--note",
            "Confirmed album version",
        ]
    )

    assert args.command == "select"
    assert args.confirmation_note == "Confirmed album version"


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


def test_reference_cli_select_delegates_explicit_confirmation(monkeypatch, capsys) -> None:
    captured: dict[str, object] = {}

    def fake_select(project, **kwargs):
        captured["project"] = project
        captured.update(kwargs)
        return Path("projects/song/sources/reference_selection.json")

    monkeypatch.setattr("rocksmith_cdlc_generator.reference_cli.select_reference_source", fake_select)
    monkeypatch.setattr(
        "sys.argv",
        [
            "cdlc-reference",
            "select",
            "projects/song",
            "https://www.youtube.com/watch?v=abc123",
            "--note",
            "Confirmed studio master",
        ],
    )

    main()

    assert captured["url"] == "https://www.youtube.com/watch?v=abc123"
    assert captured["confirmation_note"] == "Confirmed studio master"
    assert "reference_selection.json" in capsys.readouterr().out


def test_reference_cli_selected_emits_human_confirmed_json(monkeypatch, capsys) -> None:
    selection = ReferenceSelection(
        reference_url="https://www.youtube.com/watch?v=abc123",
        display_name="Official upload",
        provider="YouTube",
        version_hint="studio",
    )
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.reference_cli.load_reference_selection",
        lambda project: selection,
    )
    monkeypatch.setattr("sys.argv", ["cdlc-reference", "selected", "projects/song"])

    main()

    payload = json.loads(capsys.readouterr().out)
    assert payload["human_confirmed"] is True
    assert payload["provider"] == "YouTube"
