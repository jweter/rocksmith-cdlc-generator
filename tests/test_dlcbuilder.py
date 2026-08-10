import json

import pytest

from rocksmith_cdlc_generator.dlcbuilder import build_dlcbuilder_project
from rocksmith_cdlc_generator.models import AudioMetadata, ProjectManifest


def _manifest() -> ProjectManifest:
    return ProjectManifest(
        project_name="test-song",
        artist="Test Artist",
        title="Test Song",
        source_original_path="source.wav",
        source_project_path="source/source.wav",
        source_sha256="a" * 64,
        source_metadata=AudioMetadata(
            duration_seconds=120.0,
            sample_rate_hz=44100,
            channels=2,
            codec_name="pcm_s16le",
            format_name="wav",
        ),
    )


def test_dlcbuilder_project_matches_bass_contract() -> None:
    project = build_dlcbuilder_project(
        _manifest(),
        xml_path="../../eof/arr_bass_RS2.xml",
        audio_path="../../audio/normalized.wav",
        preview_path="preview.wav",
        album_art_path="cover.png",
        album_name="Test Album",
        year=2026,
        tuning_offsets=(-2, 0, 0, 0, 0, 0),
    )

    assert project["Version"] == "1"
    assert project["DLCKey"] == "TestArtistTestSong"
    assert project["ArtistName"]["Value"] == "Test Artist"
    assert project["AudioFile"]["Path"] == "../../audio/normalized.wav"
    arrangement = project["Arrangements"][0]
    assert arrangement["Case"] == "Instrumental"
    bass = arrangement["Fields"][0]
    assert bass["XML"] == "../../eof/arr_bass_RS2.xml"
    assert bass["Name"] == 3
    assert bass["RouteMask"] == 4
    assert bass["Tuning"] == [-2, 0, 0, 0, 0, 0]
    assert bass["BaseTone"] == "bass"
    assert bass["MasterID"] > 0


def test_multi_arrangement_project_uses_upstream_name_and_route_codes() -> None:
    project = build_dlcbuilder_project(
        _manifest(),
        audio_path="normalized.wav",
        preview_path="preview.wav",
        album_art_path="cover.png",
        album_name="Album",
        year=2026,
        arrangements={
            "bass": ("arr_bass_RS2.xml", (-2, 0, 0, 0, 0, 0)),
            "lead": ("arr_lead_RS2.xml", (0, 0, 0, 0, 0, 0)),
            "rhythm": ("arr_rhythm_RS2.xml", (-2, 0, 0, 0, 0, 0)),
        },
    )

    fields = [item["Fields"][0] for item in project["Arrangements"]]
    assert [(item["Name"], item["RouteMask"]) for item in fields] == [
        (0, 1),
        (2, 2),
        (3, 4),
    ]
    assert [item["XML"] for item in fields] == [
        "arr_lead_RS2.xml",
        "arr_rhythm_RS2.xml",
        "arr_bass_RS2.xml",
    ]
    assert fields[0]["BaseTone"] == "guitar"
    assert fields[1]["BaseTone"] == "guitar"
    assert fields[2]["BaseTone"] == "bass"
    assert fields[1]["Tuning"] == [-2, 0, 0, 0, 0, 0]
    assert len({item["MasterID"] for item in fields}) == 3
    assert len({item["PersistentID"] for item in fields}) == 3


def test_ids_are_reproducible_per_arrangement() -> None:
    kwargs = dict(
        audio_path="normalized.wav",
        preview_path="preview.wav",
        album_art_path="cover.png",
        album_name="Album",
        year=2026,
        arrangements={
            "lead": ("arr_lead_RS2.xml", (0, 0, 0, 0, 0, 0)),
            "bass": ("arr_bass_RS2.xml", (0, 0, 0, 0, 0, 0)),
        },
    )
    first = build_dlcbuilder_project(_manifest(), **kwargs)
    second = build_dlcbuilder_project(_manifest(), **kwargs)

    for first_arrangement, second_arrangement in zip(first["Arrangements"], second["Arrangements"]):
        first_fields = first_arrangement["Fields"][0]
        second_fields = second_arrangement["Fields"][0]
        assert first_fields["MasterID"] == second_fields["MasterID"]
        assert first_fields["PersistentID"] == second_fields["PersistentID"]


def test_project_is_json_serializable() -> None:
    project = build_dlcbuilder_project(
        _manifest(),
        xml_path="arr_bass_RS2.xml",
        audio_path="normalized.wav",
        preview_path="preview.wav",
        album_art_path="cover.png",
        album_name="Album",
        year=2026,
        tuning_offsets=(0, 0, 0, 0, 0, 0),
    )
    parsed = json.loads(json.dumps(project))
    assert parsed["Arrangements"][0]["Fields"][0]["Name"] == 3


def test_missing_artist_is_rejected() -> None:
    manifest = _manifest().model_copy(update={"artist": None})
    with pytest.raises(ValueError, match="Artist metadata"):
        build_dlcbuilder_project(
            manifest,
            xml_path="arr_bass_RS2.xml",
            audio_path="normalized.wav",
            preview_path="preview.wav",
            album_art_path="cover.png",
            album_name="Album",
            year=2026,
            tuning_offsets=(0, 0, 0, 0, 0, 0),
        )


def test_unknown_arrangement_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported DLC Builder arrangement"):
        build_dlcbuilder_project(
            _manifest(),
            audio_path="normalized.wav",
            preview_path="preview.wav",
            album_art_path="cover.png",
            album_name="Album",
            year=2026,
            arrangements={"keys": ("arr_keys.xml", (0, 0, 0, 0, 0, 0))},
        )
