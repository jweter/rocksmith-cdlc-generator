from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from rocksmith_cdlc_generator.psarc_inspection import (
    PsarcContentError,
    PsarcContentInspection,
    evaluate_psarc_content,
    inspect_psarc_content,
)


def _inspection(**overrides) -> PsarcContentInspection:
    payload = {
        "entry_count": 12,
        "entries": ["manifests/songs_dlc_test/test.json"],
        "lead_sng": ["songs/bin/generic/test_lead.sng"],
        "rhythm_sng": ["songs/bin/generic/test_rhythm.sng"],
        "bass_sng": ["songs/bin/generic/test_bass.sng"],
        "manifests": ["manifests/songs_dlc_test/test.json"],
        "audio_wem": ["audio/windows/song_test.wem"],
        "sound_banks": ["audio/windows/song_test.bnk"],
        "xblocks": ["gamexblocks/nsongs/test.xblock"],
        "album_art": ["gfxassets/album_art/album_test.dds"],
    }
    payload.update(overrides)
    return PsarcContentInspection(**payload)


def test_evaluate_psarc_content_passes_three_arrangement_package():
    result = evaluate_psarc_content(["bass", "lead", "rhythm"], _inspection())

    assert result.status == "PASS"
    assert result.failures == []


def test_evaluate_psarc_content_rejects_missing_configured_arrangement():
    result = evaluate_psarc_content(
        ["bass", "lead", "rhythm"],
        _inspection(rhythm_sng=[]),
    )

    assert result.status == "FAIL"
    assert "Built PSARC contains no Rhythm SNG arrangement" in result.failures


def test_evaluate_psarc_content_rejects_missing_core_assets():
    result = evaluate_psarc_content(
        ["bass"],
        _inspection(manifests=[], audio_wem=[], sound_banks=[], xblocks=[], album_art=[]),
    )

    assert result.status == "FAIL"
    assert len(result.failures) == 5


def test_inspect_psarc_content_parses_bridge_json(tmp_path, monkeypatch):
    bridge = tmp_path / "bridge.exe"
    bridge.write_bytes(b"bridge")
    psarc = tmp_path / "test_p.psarc"
    psarc.write_bytes(b"PSAR")
    stdout = json.dumps(
        {
            "upstreamCommit": "abc",
            "entryCount": 12,
            "entries": ["entry"],
            "leadSng": ["test_lead.sng"],
            "rhythmSng": ["test_rhythm.sng"],
            "bassSng": ["test_bass.sng"],
            "manifests": ["manifest.json"],
            "audioWem": ["song.wem"],
            "soundBanks": ["song.bnk"],
            "xblocks": ["song.xblock"],
            "albumArt": ["album.dds"],
        }
    )
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.psarc_inspection.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(stdout=stdout, stderr=""),
    )

    result = inspect_psarc_content(psarc, bridge_path=bridge)

    assert result.upstream_commit == "abc"
    assert result.lead_sng == ["test_lead.sng"]
    assert result.rhythm_sng == ["test_rhythm.sng"]
    assert result.bass_sng == ["test_bass.sng"]


def test_inspect_psarc_content_rejects_invalid_bridge_json(tmp_path, monkeypatch):
    bridge = tmp_path / "bridge.exe"
    bridge.write_bytes(b"bridge")
    psarc = tmp_path / "test_p.psarc"
    psarc.write_bytes(b"PSAR")
    monkeypatch.setattr(
        "rocksmith_cdlc_generator.psarc_inspection.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(stdout="not-json", stderr=""),
    )

    with pytest.raises(PsarcContentError, match="invalid inspection JSON"):
        inspect_psarc_content(psarc, bridge_path=bridge)
