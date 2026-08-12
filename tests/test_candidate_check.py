from __future__ import annotations

import json
from pathlib import Path

import pytest

from rocksmith_cdlc_generator.candidate_check import (
    CandidateCheckError,
    check_candidate,
    load_cfsm_catalog,
    normalize_name,
    summarize_catalog,
)


def _write_catalog(tmp_path: Path, payload: object) -> Path:
    path = tmp_path / "SongsMasterGrid.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_normalize_name_is_deterministic_for_punctuation_and_case() -> None:
    assert normalize_name("Lamb of God") == normalize_name("LAMB-OF-GOD")
    assert normalize_name("Motörhead") == normalize_name("Motorhead")


def test_loads_top_level_cfsm_rows_and_metadata(tmp_path: Path) -> None:
    path = _write_catalog(
        tmp_path,
        [
            {
                "Artist": "Lamb of God",
                "SongTitle": "Laid to Rest",
                "Arrangements": "Lead; Rhythm; Bass",
                "Tuning": "Drop D",
            }
        ],
    )

    songs, digest, modified = load_cfsm_catalog(path)

    assert len(songs) == 1
    assert songs[0].artist == "Lamb of God"
    assert songs[0].arrangements == ("Lead", "Rhythm", "Bass")
    assert songs[0].tunings == ("Drop D",)
    assert songs[0].library_kind == "unknown"
    assert len(digest) == 64
    assert modified.endswith("+00:00")


def test_supports_real_cfsm_song_manager_export_shape(tmp_path: Path) -> None:
    path = _write_catalog(
        tmp_path,
        {
            "dgvSongsMaster": [
                {
                    "rowId": 0,
                    "colArtist": "3 Doors Down",
                    "colTitle": "Loser",
                    "colArrangements": "Bass, Combo1, Combo2, Vocals",
                    "colTunings": "E Standard, E Standard, E Standard",
                    "colRepairStatus": "ODLC",
                    "colTagged": "ODLC",
                    "colFilePath": r"C:\\Program Files (x86)\\Steam\\steamapps\\common\\Rocksmith2014\\dlc\\example.psarc",
                },
                {
                    "rowId": 1,
                    "colArtist": "A Perfect Circle",
                    "colTitle": "The Noose",
                    "colArrangements": "Bass, Lead, Rhythm",
                    "colTunings": "C# Standard, C# Standard, C# Standard",
                    "colRepairStatus": "RepairedDD",
                    "colTagged": "False",
                },
            ]
        },
    )

    songs, _, _ = load_cfsm_catalog(path)

    assert [(song.artist, song.title) for song in songs] == [
        ("3 Doors Down", "Loser"),
        ("A Perfect Circle", "The Noose"),
    ]
    assert songs[0].arrangements == ("Bass", "Combo1", "Combo2", "Vocals")
    assert songs[0].tunings == ("E Standard", "E Standard", "E Standard")
    assert songs[0].library_kind == "official_dlc"
    assert songs[1].library_kind == "custom_or_local"


def test_supports_named_row_container_and_field_aliases(tmp_path: Path) -> None:
    path = _write_catalog(
        tmp_path,
        {
            "SongsMasterGrid": [
                {"ArtistName": "Trivium", "Title": "Built to Fall"},
            ]
        },
    )

    songs, _, _ = load_cfsm_catalog(path)

    assert [(song.artist, song.title) for song in songs] == [("Trivium", "Built to Fall")]


def test_exact_match_wins_and_reports_same_artist(tmp_path: Path) -> None:
    path = _write_catalog(
        tmp_path,
        [
            {"Artist": "Lamb of God", "SongTitle": "Laid to Rest", "Arrangement": "Bass"},
            {"Artist": "Lamb of God", "SongTitle": "Redneck"},
        ],
    )

    result = check_candidate(path, artist="Lamb of God", title="Laid to Rest")

    assert result.match_type == "exact"
    assert [item.title for item in result.matches] == ["Laid to Rest"]
    assert [item.title for item in result.same_artist] == ["Laid to Rest", "Redneck"]


def test_normalized_match_handles_punctuation_without_fuzzy_guessing(tmp_path: Path) -> None:
    path = _write_catalog(
        tmp_path,
        [{"Artist": "AC/DC", "SongTitle": "Hells Bells"}],
    )

    result = check_candidate(path, artist="ACDC", title="Hells Bells")

    assert result.match_type == "normalized"
    assert len(result.matches) == 1


def test_ambiguous_normalized_matches_remain_ambiguous(tmp_path: Path) -> None:
    path = _write_catalog(
        tmp_path,
        [
            {"Artist": "Example", "SongTitle": "Song-One"},
            {"Artist": "Example", "SongTitle": "Song One"},
        ],
    )

    result = check_candidate(path, artist="Example", title="Song One")

    assert result.match_type == "ambiguous_normalized"
    assert len(result.matches) == 2


def test_identical_exact_duplicates_remain_ambiguously_exact(tmp_path: Path) -> None:
    path = _write_catalog(
        tmp_path,
        [
            {"Artist": "Example", "SongTitle": "Song One", "Arrangement": "Lead"},
            {"Artist": "Example", "SongTitle": "Song One", "Arrangement": "Bass"},
        ],
    )

    result = check_candidate(path, artist="Example", title="Song One")

    assert result.match_type == "ambiguous_exact"
    assert len(result.matches) == 2


def test_none_match_still_returns_same_artist_context(tmp_path: Path) -> None:
    path = _write_catalog(
        tmp_path,
        [{"Artist": "Trivium", "SongTitle": "In Waves"}],
    )

    result = check_candidate(path, artist="Trivium", title="Built to Fall")

    assert result.match_type == "none"
    assert result.matches == ()
    assert [item.title for item in result.same_artist] == ["In Waves"]


def test_summarize_catalog_reports_normalized_identity_and_metadata_counts(tmp_path: Path) -> None:
    path = _write_catalog(
        tmp_path,
        {
            "dgvSongsMaster": [
                {
                    "colArtist": "AC/DC",
                    "colTitle": "Back in Black",
                    "colArrangements": "Bass, Lead, Rhythm, Vocals",
                    "colTunings": "E Standard, E Standard, E Standard",
                    "colRepairStatus": "ODLC",
                    "colTagged": "ODLC",
                },
                {
                    "colArtist": "ACDC",
                    "colTitle": "Back-In-Black",
                    "colArrangements": "Bass, Lead, Rhythm",
                    "colTunings": "E Standard, E Standard, E Standard",
                    "colRepairStatus": "RepairedDD",
                    "colTagged": "False",
                },
                {
                    "colArtist": "Ghost",
                    "colTitle": "Ritual",
                    "colArrangements": "Bass, Lead, Rhythm",
                    "colTunings": "D Standard, D Standard, D Standard",
                },
            ]
        },
    )

    summary = summarize_catalog(path)

    assert summary.row_count == 3
    assert summary.unique_artist_count == 2
    assert summary.unique_song_count == 2
    assert summary.library_kind_counts == {
        "official_dlc": 1,
        "custom_or_local": 1,
        "unknown": 1,
    }
    assert summary.arrangement_counts == {"Bass": 3, "Lead": 3, "Rhythm": 3, "Vocals": 1}
    assert summary.tuning_counts == {"E Standard": 6, "D Standard": 3}
    assert len(summary.catalog_sha256) == 64
    assert summary.catalog_modified_utc.endswith("+00:00")


def test_summary_is_read_only_and_omits_live_psarc_paths(tmp_path: Path) -> None:
    path = _write_catalog(
        tmp_path,
        {
            "dgvSongsMaster": [
                {
                    "colArtist": "Lamb of God",
                    "colTitle": "Redneck",
                    "colArrangements": "Bass, Lead",
                    "colTunings": "Drop D, Drop D",
                    "colRepairStatus": "ODLC",
                    "colFilePath": r"C:\\Program Files (x86)\\Steam\\steamapps\\common\\Rocksmith2014\\dlc\\redneck.psarc",
                }
            ]
        },
    )
    before = path.read_bytes()

    payload = summarize_catalog(path).to_dict()

    assert path.read_bytes() == before
    assert "psarc" not in json.dumps(payload).casefold()


def test_rejects_unrecognized_or_empty_catalogs(tmp_path: Path) -> None:
    path = _write_catalog(tmp_path, {"unexpected": []})
    with pytest.raises(CandidateCheckError, match="row list"):
        load_cfsm_catalog(path)

    path = _write_catalog(tmp_path, [{"Album": "No artist/title"}])
    with pytest.raises(CandidateCheckError, match="recognizable artist/title"):
        load_cfsm_catalog(path)


def test_result_is_read_only_and_does_not_change_catalog(tmp_path: Path) -> None:
    path = _write_catalog(tmp_path, [{"Artist": "Ghost", "SongTitle": "Ritual"}])
    before = path.read_bytes()

    result = check_candidate(path, artist="Ghost", title="Ritual")

    assert result.to_dict()["catalog"]["sha256"]
    assert path.read_bytes() == before
