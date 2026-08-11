from pathlib import Path

import pytest

from rocksmith_cdlc_generator.local_psarc_workspace import (
    VerifiedPsarcCopy,
    assert_private_destination,
    copy_psarc_for_inspection,
    inspection_output_dir,
)


def test_copy_psarc_is_hash_verified_and_reused(tmp_path: Path) -> None:
    rocksmith = tmp_path / "Rocksmith2014"
    dlc = rocksmith / "dlc"
    dlc.mkdir(parents=True)
    source = dlc / "song_p.psarc"
    source.write_bytes(b"PSAR-reference-data")
    workspace = tmp_path / "private" / "rocksmith_library"

    first = copy_psarc_for_inspection(source, workspace_root=workspace, rocksmith_root=rocksmith)
    second = copy_psarc_for_inspection(source, workspace_root=workspace, rocksmith_root=rocksmith)

    assert first.verified
    assert first.copy == second.copy
    assert first.copy.read_bytes() == source.read_bytes()
    assert first.copy.is_relative_to(workspace)
    assert not first.copy.is_relative_to(rocksmith)


def test_rejects_workspace_inside_live_install(tmp_path: Path) -> None:
    rocksmith = tmp_path / "Rocksmith2014"
    dlc = rocksmith / "dlc"
    dlc.mkdir(parents=True)
    source = dlc / "song.psarc"
    source.write_bytes(b"PSAR")

    with pytest.raises(ValueError, match="live Rocksmith"):
        copy_psarc_for_inspection(
            source,
            workspace_root=rocksmith / "inspection",
            rocksmith_root=rocksmith,
        )


def test_rejects_source_outside_configured_install(tmp_path: Path) -> None:
    rocksmith = tmp_path / "Rocksmith2014"
    rocksmith.mkdir()
    source = tmp_path / "elsewhere.psarc"
    source.write_bytes(b"PSAR")

    with pytest.raises(ValueError, match="configured Rocksmith"):
        copy_psarc_for_inspection(
            source,
            workspace_root=tmp_path / "private",
            rocksmith_root=rocksmith,
        )


def test_inspection_output_requires_verified_copy(tmp_path: Path) -> None:
    rocksmith = tmp_path / "Rocksmith2014"
    rocksmith.mkdir()
    workspace = tmp_path / "private"
    fake = VerifiedPsarcCopy(
        source=rocksmith / "dlc" / "a.psarc",
        copy=workspace / "a.psarc",
        source_sha256="a" * 64,
        copy_sha256="b" * 64,
    )
    with pytest.raises(ValueError, match="unverified"):
        inspection_output_dir(fake, workspace_root=workspace, rocksmith_root=rocksmith)


def test_private_destination_guard_rejects_install_descendant(tmp_path: Path) -> None:
    rocksmith = tmp_path / "Rocksmith2014"
    rocksmith.mkdir()
    with pytest.raises(ValueError):
        assert_private_destination(rocksmith / "dlc" / "temp", rocksmith_root=rocksmith)
