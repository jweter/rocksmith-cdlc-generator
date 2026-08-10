import json
from pathlib import Path

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


def test_ids_are_reproducible() -> None:
    kwargs = dict(
        xml_path="arr_bass_RS2.xml",
        audio_path="normalized.wav",
        preview_path="preview.wav",
        album_art_path="cover.png",
        album_name="Album",
        year=2026,
        tuning_offsets=(0, 0, 0, 0, 0, 0),
    )
    first = build_dlcbuilder_project(_manifest(), **kwargs)
    second = build_dlcbuilder_project(_manifest(), **kwargs)

    first_bass = first["Arrangements"][0]["Fields"][0]
    second_bass = second["Arrangements"][0]["Fields"][0]
    assert first_bass["MasterID"] == second_bass["MasterID"]
    assert first_bass["PersistentID"] == second_bass["PersistentID"]


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
