from __future__ import annotations

import json
import sys
from pathlib import Path

from rocksmith_cdlc_generator.cli import build_parser, main


def _write_catalog(tmp_path: Path) -> Path:
    path = tmp_path / "SongsMasterGrid.json"
    path.write_text(
        json.dumps(
            {
                "dgvSongsMaster": [
                    {
                        "colArtist": "AC/DC",
                        "colTitle": "Back in Black",
                        "colArrangements": "Bass, Lead, Rhythm, Vocals",
                        "colTunings": "E Standard, E Standard, E Standard",
                        "colRepairStatus": "ODLC",
                        "colTagged": "ODLC",
                        "colFilePath": r"C:\\Rocksmith2014\\dlc\\back_in_black.psarc",
                    },
                    {
                        "colArtist": "Ghost",
                        "colTitle": "Ritual",
                        "colArrangements": "Bass, Lead, Rhythm",
                        "colTunings": "D Standard, D Standard, D Standard",
                        "colRepairStatus": "RepairedDD",
                        "colTagged": "False",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    return path


def test_library_summary_parser_requires_catalog() -> None:
    args = build_parser().parse_args(["library-summary", "--catalog", "library.json"])

    assert args.command == "library-summary"
    assert args.catalog == Path("library.json")


def test_library_summary_cli_outputs_read_only_json(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    catalog = _write_catalog(tmp_path)
    before = catalog.read_bytes()
    monkeypatch.setattr(sys, "argv", ["cdlc", "library-summary", "--catalog", str(catalog)])

    main()

    payload = json.loads(capsys.readouterr().out)
    assert payload["row_count"] == 2
    assert payload["unique_artist_count"] == 2
    assert payload["unique_song_count"] == 2
    assert payload["library_kind_counts"] == {
        "official_dlc": 1,
        "custom_or_local": 1,
        "unknown": 0,
    }
    assert payload["arrangement_counts"]["Bass"] == 2
    assert payload["tuning_counts"] == {"E Standard": 3, "D Standard": 3}
    assert len(payload["catalog"]["sha256"]) == 64
    assert "psarc" not in json.dumps(payload).casefold()
    assert catalog.read_bytes() == before
