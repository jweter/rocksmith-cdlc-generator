from __future__ import annotations

import json
from pathlib import Path

from rocksmith_cdlc_generator.candidate_check import check_candidate, normalize_name, summarize_catalog


def _write_catalog(tmp_path: Path, rows: list[dict[str, str]]) -> Path:
    path = tmp_path / "SongsMasterGrid.json"
    path.write_text(json.dumps({"dgvSongsMaster": rows}), encoding="utf-8")
    return path


def test_punctuation_only_names_keep_distinct_normalized_identities() -> None:
    assert normalize_name("!!!") == "!!!"
    assert normalize_name("???") == "???"
    assert normalize_name("!!!") != normalize_name("???")


def test_candidate_matcher_does_not_conflate_punctuation_only_artists(tmp_path: Path) -> None:
    path = _write_catalog(
        tmp_path,
        [
            {"colArtist": "!!!", "colTitle": "Song"},
            {"colArtist": "???", "colTitle": "Song"},
        ],
    )

    result = check_candidate(path, artist="!!!", title="Song")

    assert result.match_type == "exact"
    assert [(item.artist, item.title) for item in result.matches] == [("!!!", "Song")]
    assert [(item.artist, item.title) for item in result.same_artist] == [("!!!", "Song")]


def test_summary_uses_same_identity_semantics_as_candidate_matching(tmp_path: Path) -> None:
    path = _write_catalog(
        tmp_path,
        [
            {"colArtist": "!!!", "colTitle": "Song"},
            {"colArtist": "???", "colTitle": "Song"},
        ],
    )

    summary = summarize_catalog(path)

    assert summary.row_count == 2
    assert summary.unique_artist_count == 2
    assert summary.unique_song_count == 2
