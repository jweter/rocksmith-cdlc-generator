from __future__ import annotations

import json
from pathlib import Path

from rocksmith_cdlc_generator.candidate_check import check_candidate, normalize_name, summarize_catalog


def _write_catalog(tmp_path: Path, rows: list[dict[str, str]]) -> Path:
    path = tmp_path / "SongsMasterGrid.json"
    path.write_text(json.dumps({"dgvSongsMaster": rows}, ensure_ascii=False), encoding="utf-8")
    return path


def test_punctuation_only_normalization_preserves_distinct_identity() -> None:
    assert normalize_name("!!!") == "!!!"
    assert normalize_name("???") == "???"
    assert normalize_name("!!!") != normalize_name("???")


def test_punctuation_only_normalization_converges_unicode_equivalents() -> None:
    assert normalize_name("…") == normalize_name("...")
    assert normalize_name("！") == normalize_name("!")
    assert normalize_name(";") == normalize_name(";")


def test_candidate_matching_uses_unicode_normalized_punctuation_identity(tmp_path: Path) -> None:
    path = _write_catalog(tmp_path, [{"colArtist": "…", "colTitle": "！"}])

    result = check_candidate(path, artist="...", title="!")

    assert result.match_type == "normalized"
    assert len(result.matches) == 1


def test_summary_uses_same_unicode_punctuation_identity(tmp_path: Path) -> None:
    path = _write_catalog(
        tmp_path,
        [
            {"colArtist": "…", "colTitle": "！"},
            {"colArtist": "...", "colTitle": "!"},
            {"colArtist": "???", "colTitle": "!"},
        ],
    )

    summary = summarize_catalog(path)

    assert summary.row_count == 3
    assert summary.unique_artist_count == 2
    assert summary.unique_song_count == 2
