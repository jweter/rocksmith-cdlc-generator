import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from rocksmith_cdlc_generator.local_psarc_workspace import VerifiedPsarcCopy, sha256_file
from rocksmith_cdlc_generator.private_psarc_extraction import (
    _tone_json_candidates,
    extract_verified_psarc,
)


def _verified_copy(tmp_path: Path) -> tuple[VerifiedPsarcCopy, Path, Path]:
    rocksmith_root = tmp_path / "Rocksmith2014"
    source = rocksmith_root / "dlc" / "song_p.psarc"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"PSARC fixture")
    workspace = tmp_path / "private"
    copy = workspace / "source_copies" / "song_p.psarc"
    copy.parent.mkdir(parents=True)
    copy.write_bytes(source.read_bytes())
    digest = sha256_file(source)
    return (
        VerifiedPsarcCopy(
            source=source,
            copy=copy,
            source_sha256=digest,
            copy_sha256=digest,
        ),
        rocksmith_root,
        workspace,
    )


def test_tone_candidate_detection_is_recursive(tmp_path: Path) -> None:
    with_tone = tmp_path / "tone.json"
    without_tone = tmp_path / "plain.json"
    malformed = tmp_path / "bad.json"
    with_tone.write_text(json.dumps({"Entries": [{"Attributes": {"Tone_A": "lead"}}]}), encoding="utf-8")
    without_tone.write_text(json.dumps({"Entries": [{"Attributes": {"SongName": "x"}}]}), encoding="utf-8")
    malformed.write_text("{not-json", encoding="utf-8")

    assert _tone_json_candidates([without_tone, malformed, with_tone]) == [str(with_tone)]


def test_extraction_rejects_changed_verified_copy(tmp_path: Path) -> None:
    verified, rocksmith_root, workspace = _verified_copy(tmp_path)
    verified.copy.write_bytes(b"changed")
    with pytest.raises(ValueError, match="no longer matches"):
        extract_verified_psarc(
            verified,
            workspace_root=workspace,
            rocksmith_root=rocksmith_root,
            bridge_path=tmp_path / "bridge.exe",
        )


def test_extraction_uses_verified_copy_and_private_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    verified, rocksmith_root, workspace = _verified_copy(tmp_path)
    bridge = tmp_path / "bridge.exe"
    bridge.write_bytes(b"fixture")

    def fake_run(command, **kwargs):
        assert kwargs["check"] is True
        assert command[1] == "extract"
        assert Path(command[2]).resolve() == verified.copy.resolve()
        output = Path(command[3]).resolve()
        assert output.is_relative_to(workspace.resolve())
        manifest = output / "manifests" / "song.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps({"Attributes": {"Tone_Base": "clean"}}), encoding="utf-8")
        sng = output / "songs" / "bin" / "generic" / "song_lead.sng"
        sng.parent.mkdir(parents=True, exist_ok=True)
        sng.write_bytes(b"SNG")
        payload = {
            "entryCount": 2,
            "jsonFiles": [str(manifest)],
            "sngFiles": [str(sng)],
        }
        return SimpleNamespace(stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr("rocksmith_cdlc_generator.private_psarc_extraction.subprocess.run", fake_run)
    result = extract_verified_psarc(
        verified,
        workspace_root=workspace,
        rocksmith_root=rocksmith_root,
        bridge_path=bridge,
    )

    assert result.entry_count == 2
    assert result.verified_copy == str(verified.copy.resolve())
    assert len(result.tone_json_candidates) == 1
    assert Path(result.extracted_directory).is_relative_to(workspace.resolve())


def test_bridge_paths_outside_private_output_are_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    verified, rocksmith_root, workspace = _verified_copy(tmp_path)
    bridge = tmp_path / "bridge.exe"
    bridge.write_bytes(b"fixture")
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")

    def fake_run(command, **kwargs):
        return SimpleNamespace(
            stdout=json.dumps({"entryCount": 1, "jsonFiles": [str(outside)], "sngFiles": []}),
            stderr="",
        )

    monkeypatch.setattr("rocksmith_cdlc_generator.private_psarc_extraction.subprocess.run", fake_run)
    with pytest.raises(ValueError, match="outside the private workspace"):
        extract_verified_psarc(
            verified,
            workspace_root=workspace,
            rocksmith_root=rocksmith_root,
            bridge_path=bridge,
        )
