from __future__ import annotations

import json
import sys
from pathlib import Path

from rocksmith_cdlc_generator.cli import build_parser, main


def _write_real_shape_catalog(tmp_path: Path) -> Path:
    path = tmp_path / "SongsMasterGrid.json"
    path.write_text(
        json.dumps(
            {
                "dgvSongsMaster": [
                    {
                        "rowId": 0,
                        "colArtist": "Lamb of God",
                        "colTitle": "Redneck",
                        "colArrangements": "Bass, Lead, Rhythm, Vocals",
                        "colTunings": "Drop D, Drop D, Drop D",
                        "colRepairStatus": "ODLC",
                        "colTagged": "ODLC",
                    },
                    {
                        "rowId": 1,
                        "colArtist": "Mastodon",
                        "colTitle": "The Motherload",
                        "colArrangements": "Bass, Lead, Rhythm, Vocals",
                        "colTunings": "D Drop C, D Drop C, D Drop C",
                        "colRepairStatus": "RepairedDD",
                        "colTagged": "False",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    return path


def test_candidate_check_parser_contract(tmp_path: Path) -> None:
    catalog = _write_real_shape_catalog(tmp_path)

    args = build_parser().parse_args(
        [
            "candidate-check",
            "--catalog",
            str(catalog),
            "--artist",
            "Mastodon",
            "--title",
            "The Motherload",
        ]
    )

    assert args.command == "candidate-check"
    assert args.catalog == catalog
    assert args.artist == "Mastodon"
    assert args.title == "The Motherload"


def test_candidate_check_cli_prints_machine_readable_exact_match(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    catalog = _write_real_shape_catalog(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "cdlc",
            "candidate-check",
            "--catalog",
            str(catalog),
            "--artist",
            "Mastodon",
            "--title",
            "The Motherload",
        ],
    )

    main()

    payload = json.loads(capsys.readouterr().out)
    assert payload["match_type"] == "exact"
    assert payload["matches"][0]["artist"] == "Mastodon"
    assert payload["matches"][0]["title"] == "The Motherload"
    assert payload["matches"][0]["library_kind"] == "custom_or_local"
    assert payload["matches"][0]["arrangements"] == ["Bass", "Lead", "Rhythm", "Vocals"]
    assert payload["catalog"]["sha256"]


def test_candidate_check_cli_preserves_no_match_and_same_artist_context(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    catalog = _write_real_shape_catalog(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "cdlc",
            "candidate-check",
            "--catalog",
            str(catalog),
            "--artist",
            "Lamb of God",
            "--title",
            "Laid to Rest",
        ],
    )

    main()

    payload = json.loads(capsys.readouterr().out)
    assert payload["match_type"] == "none"
    assert payload["matches"] == []
    assert [item["title"] for item in payload["same_artist"]] == ["Redneck"]
