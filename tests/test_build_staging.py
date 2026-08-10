from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from rocksmith_cdlc_generator import build_staging


def _write_dlcbuilder_fixture(tmp_path):
    project_dir = tmp_path / "project"
    dlc_dir = project_dir / "build" / "dlcbuilder"
    dlc_dir.mkdir(parents=True)

    for name, payload in {
        "song.wav": b"song-audio",
        "preview.wav": b"preview-audio",
        "cover.png": b"cover-art",
        "arr_bass_RS2.xml": b"<song version='7'/>",
    }.items():
        (dlc_dir / name).write_bytes(payload)

    rs2dlc = dlc_dir / "TestSong.rs2dlc"
    rs2dlc.write_text(
        json.dumps(
            {
                "AudioFile": {"Path": "song.wav"},
                "AudioPreviewFile": {"Path": "preview.wav"},
                "AlbumArtFile": "cover.png",
                "Arrangements": [
                    {
                        "Case": "Instrumental",
                        "Fields": [{"Name": 3, "XML": "arr_bass_RS2.xml"}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return project_dir, rs2dlc


def test_inspect_dlcbuilder_assets_hashes_all_required_inputs(tmp_path):
    _, rs2dlc = _write_dlcbuilder_fixture(tmp_path)

    assets = build_staging.inspect_dlcbuilder_assets(rs2dlc)

    assert {asset.role for asset in assets} == {
        "song_audio",
        "preview_audio",
        "album_art",
        "bass_xml",
    }
    assert all(asset.size_bytes > 0 for asset in assets)
    assert all(len(asset.sha256) == 64 for asset in assets)


def test_stage_build_writes_readiness_manifest_without_live_install(tmp_path, monkeypatch):
    project_dir, rs2dlc = _write_dlcbuilder_fixture(tmp_path)
    monkeypatch.setattr(
        build_staging,
        "require_packaging_ready",
        lambda _: SimpleNamespace(status="PASS"),
    )

    output = build_staging.stage_build(project_dir, dlcbuilder_project=rs2dlc)
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert payload["validation_status"] == "PASS"
    assert payload["safe_for_manual_packaging"] is True
    assert payload["writes_to_live_rocksmith_install"] is False
    assert len(payload["assets"]) == 4
    assert (project_dir / "build" / "staging" / "BUILD_INSTRUCTIONS.md").is_file()


def test_register_psarc_checks_header_and_stages_copy(tmp_path, monkeypatch):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    monkeypatch.setattr(
        build_staging,
        "require_packaging_ready",
        lambda _: SimpleNamespace(status="PASS"),
    )
    psarc = tmp_path / "test_p.psarc"
    psarc.write_bytes(b"PSAR" + b"\x00\x01\x00\x04" + b"zlib" + b"payload")

    receipt_path = build_staging.register_psarc(project_dir, psarc)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

    assert receipt["magic"] == "PSAR"
    assert receipt["basic_integrity"] == "PASS"
    assert receipt["installed_to_rocksmith"] is False
    assert receipt["size_bytes"] == psarc.stat().st_size
    assert (project_dir / "build" / "staging" / "psarc" / psarc.name).is_file()


def test_register_psarc_rejects_non_psarc_header(tmp_path, monkeypatch):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    monkeypatch.setattr(
        build_staging,
        "require_packaging_ready",
        lambda _: SimpleNamespace(status="PASS"),
    )
    psarc = tmp_path / "bad.psarc"
    psarc.write_bytes(b"NOTAPSARCFILE")

    with pytest.raises(ValueError, match="header magic"):
        build_staging.register_psarc(project_dir, psarc)
