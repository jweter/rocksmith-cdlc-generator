from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from rocksmith_cdlc_generator import build_staging


def _write_dlcbuilder_fixture(tmp_path, *, multi: bool = False):
    project_dir = tmp_path / "project"
    dlc_dir = project_dir / "build" / "dlcbuilder"
    dlc_dir.mkdir(parents=True)

    files = {
        "song.wav": b"song-audio",
        "preview.wav": b"preview-audio",
        "cover.png": b"cover-art",
        "arr_bass_RS2.xml": b"<song version='7'/>",
    }
    arrangements = [
        {
            "Case": "Instrumental",
            "Fields": [{"Name": 3, "XML": "arr_bass_RS2.xml"}],
        }
    ]
    if multi:
        files.update(
            {
                "arr_lead_RS2.xml": b"<song version='7'/>",
                "arr_rhythm_RS2.xml": b"<song version='7'/>",
            }
        )
        arrangements = [
            {
                "Case": "Instrumental",
                "Fields": [{"Name": 0, "XML": "arr_lead_RS2.xml"}],
            },
            {
                "Case": "Instrumental",
                "Fields": [{"Name": 2, "XML": "arr_rhythm_RS2.xml"}],
            },
            *arrangements,
        ]

    for name, payload in files.items():
        (dlc_dir / name).write_bytes(payload)

    rs2dlc = dlc_dir / "TestSong.rs2dlc"
    rs2dlc.write_text(
        json.dumps(
            {
                "AudioFile": {"Path": "song.wav"},
                "AudioPreviewFile": {"Path": "preview.wav"},
                "AlbumArtFile": "cover.png",
                "Arrangements": arrangements,
            }
        ),
        encoding="utf-8",
    )
    return project_dir, rs2dlc


def _write_valid_psarc(path):
    header = (
        b"PSAR"
        + b"\x00\x01\x00\x04"
        + b"zlib"
        + (32).to_bytes(4, "big")
        + (30).to_bytes(4, "big")
        + (1).to_bytes(4, "big")
        + (65536).to_bytes(4, "big")
        + (4).to_bytes(4, "big")
    )
    path.write_bytes(header + b"payload")


def _patch_gate(monkeypatch):
    monkeypatch.setattr(
        build_staging,
        "require_configured_arrangements_ready",
        lambda _: SimpleNamespace(status="PASS"),
    )


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


def test_inspect_dlcbuilder_assets_hashes_lead_rhythm_and_bass(tmp_path):
    _, rs2dlc = _write_dlcbuilder_fixture(tmp_path, multi=True)

    assets = build_staging.inspect_dlcbuilder_assets(rs2dlc)

    assert {asset.role for asset in assets} == {
        "song_audio",
        "preview_audio",
        "album_art",
        "lead_xml",
        "rhythm_xml",
        "bass_xml",
    }


def test_stage_build_writes_hashed_readiness_manifest_without_live_install(tmp_path, monkeypatch):
    project_dir, rs2dlc = _write_dlcbuilder_fixture(tmp_path)
    _patch_gate(monkeypatch)

    output = build_staging.stage_build(project_dir, dlcbuilder_project=rs2dlc)
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert payload["schema_version"] == 2
    assert payload["validation_status"] == "PASS"
    assert len(payload["dlcbuilder_project_sha256"]) == 64
    assert payload["safe_for_manual_packaging"] is True
    assert payload["writes_to_live_rocksmith_install"] is False
    assert len(payload["assets"]) == 4
    assert (project_dir / "build" / "staging" / "BUILD_INSTRUCTIONS.md").is_file()


def test_register_psarc_binds_receipt_to_staged_inputs_and_header(tmp_path, monkeypatch):
    project_dir, rs2dlc = _write_dlcbuilder_fixture(tmp_path, multi=True)
    _patch_gate(monkeypatch)
    readiness_path = build_staging.stage_build(project_dir, dlcbuilder_project=rs2dlc)

    psarc = tmp_path / "test_p.psarc"
    _write_valid_psarc(psarc)

    receipt_path = build_staging.register_psarc(project_dir, psarc)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

    assert receipt["schema_version"] == 2
    assert receipt["header"]["magic"] == "PSAR"
    assert receipt["header"]["version_major"] == 1
    assert receipt["header"]["version_minor"] == 4
    assert receipt["header"]["compression_method"] == "zlib"
    assert receipt["header"]["encrypted"] is True
    assert receipt["basic_integrity"] == "PASS"
    assert receipt["staged_inputs_unchanged"] is True
    assert receipt["installed_to_rocksmith"] is False
    assert receipt["size_bytes"] == psarc.stat().st_size
    assert len(receipt["build_readiness_sha256"]) == 64
    assert receipt["dlcbuilder_project_sha256"] == json.loads(
        readiness_path.read_text(encoding="utf-8")
    )["dlcbuilder_project_sha256"]
    assert {asset["role"] for asset in receipt["input_assets"]} == {
        "song_audio",
        "preview_audio",
        "album_art",
        "lead_xml",
        "rhythm_xml",
        "bass_xml",
    }
    assert (project_dir / "build" / "staging" / "psarc" / psarc.name).is_file()


def test_register_psarc_rejects_changed_input_after_staging(tmp_path, monkeypatch):
    project_dir, rs2dlc = _write_dlcbuilder_fixture(tmp_path)
    _patch_gate(monkeypatch)
    build_staging.stage_build(project_dir, dlcbuilder_project=rs2dlc)

    (rs2dlc.parent / "arr_bass_RS2.xml").write_bytes(b"changed-after-stage")
    psarc = tmp_path / "test_p.psarc"
    _write_valid_psarc(psarc)

    with pytest.raises(ValueError, match="changed after staging"):
        build_staging.register_psarc(project_dir, psarc)


def test_register_psarc_requires_build_readiness_manifest(tmp_path, monkeypatch):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    _patch_gate(monkeypatch)
    psarc = tmp_path / "test_p.psarc"
    _write_valid_psarc(psarc)

    with pytest.raises(FileNotFoundError, match="Build readiness manifest"):
        build_staging.register_psarc(project_dir, psarc)


def test_register_psarc_rejects_non_psarc_header(tmp_path, monkeypatch):
    project_dir, rs2dlc = _write_dlcbuilder_fixture(tmp_path)
    _patch_gate(monkeypatch)
    build_staging.stage_build(project_dir, dlcbuilder_project=rs2dlc)
    psarc = tmp_path / "bad.psarc"
    psarc.write_bytes(b"NOTAPSARCFILE" + b"\x00" * 32)

    with pytest.raises(ValueError, match="header magic"):
        build_staging.register_psarc(project_dir, psarc)
